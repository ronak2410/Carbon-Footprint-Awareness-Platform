"""AURA Carbon Footprint Analytics Platform API core.

FastAPI backend handling emission calculations, persistent logging,
history retrieval, static-file serving, and health monitoring.

Design principles applied:

- **Type annotations** — full PEP 484 coverage; re-exported via ``__all__``
- **Pydantic v2 validators** — field-level range constraints + ISO-date regex
- **Structured logging** — stdlib ``logging`` with ISO-8601 timestamps
- **Security headers** — CSP, HSTS, X-Frame-Options, Referrer-Policy on every response
- **Scoped CORS** — explicit origin allowlist; no wildcard
- **Request body size limit** — 64 KB hard cap via middleware
- **Parameterised SQL only** — no string interpolation anywhere
- **Context-manager DB connections** — guaranteed handle release (WAL + FK on)
- **DB index** — ``timestamp`` column indexed for O(log n) ordering queries
- **Health endpoint** — ``/api/health`` for uptime monitoring and Docker HEALTHCHECK

References:
    - IPCC AR6 (2021): emission factors used for calculations
    - IEA (2023): India grid average electricity emission intensity
    - UNFCCC Paris Agreement (2015): 2 t CO₂e / person / year target
"""

from __future__ import annotations

__all__ = [
    "app",
    "init_db",
    "FootprintInput",
    "DB_PATH",
    "CO2E_ELECTRICITY_FACTOR",
    "CO2E_PETROL_FACTOR",
    "CO2E_LPG_FACTOR",
    "CO2E_MEAT_MEAL_FACTOR",
    "CO2E_PLANT_MEAL_FACTOR",
    "WEEKS_PER_MONTH",
    "GLOBAL_AVERAGE_MONTHLY_KG",
    "TARGET_MONTHLY_KG",
]

import logging
import os
import re
import sqlite3
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger: logging.Logger = logging.getLogger("aura_carbon")

# ---------------------------------------------------------------------------
# Application Setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AURA Carbon Analytics API",
    description=(
        "REST API powering the AURA Carbon Footprint Awareness Platform. "
        "Provides real-time emission calculations, persistent logging, "
        "history retrieval, and data export endpoints.\n\n"
        "All endpoints return JSON. POST bodies must be ``application/json``."
    ),
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contact={
        "name": "AURA Carbon Team",
        "url": "https://github.com/ronak2410/Carbon-Footprint-Awareness-Platform",
    },
    license_info={"name": "MIT"},
)

# ---------------------------------------------------------------------------
# CORS — narrow allowlist; no wildcard origins
# ---------------------------------------------------------------------------
_ALLOWED_ORIGINS: list[str] = [
    "https://ronak2410-carbon-footprint-dashboard.hf.space",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:7860",
    "http://127.0.0.1:7860",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
    max_age=600,
)

# ---------------------------------------------------------------------------
# Request Body Size Limit Middleware (64 KB)
# ---------------------------------------------------------------------------
_MAX_BODY_BYTES: int = 64 * 1024  # 64 KB


@app.middleware("http")
async def limit_request_body(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Reject requests whose body exceeds ``_MAX_BODY_BYTES`` (64 KB).

    Args:
        request: The incoming HTTP request.
        call_next: The next middleware / route handler in the chain.

    Returns:
        A 413 JSON response if the body is too large, otherwise the normal
        response from the downstream handler.
    """
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_BODY_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": "Request body too large. Maximum allowed size is 64 KB."},
        )
    response: Response = await call_next(request)
    return response


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    ),
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next: Any) -> Response:
    """Attach security headers to every HTTP response.

    Args:
        request: The incoming HTTP request.
        call_next: The next middleware / route handler in the chain.

    Returns:
        The downstream response with all security headers appended.
    """
    response: Response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers[header] = value
    return response


# ---------------------------------------------------------------------------
# Type Aliases
# ---------------------------------------------------------------------------
# These aliases document the shape of the data dictionaries returned by
# the internal ``_compute_emissions`` helper and make callers self-documenting.
BreakdownDict = dict[str, float]
TotalsDict = dict[str, float]
ComparisonsDict = dict[str, Any]
EmissionResult = dict[str, Any]
HistoryEntry = dict[str, Any]

# ---------------------------------------------------------------------------
# Database Configuration
# ---------------------------------------------------------------------------
DB_PATH: str = os.environ.get("DB_PATH", "friday_carbon.db")

# ---------------------------------------------------------------------------
# Emission Factor Constants (IPCC / IEA)
# ---------------------------------------------------------------------------
CO2E_ELECTRICITY_FACTOR: float = 0.85
"""kg CO₂e emitted per kWh of electricity (India grid average, IEA 2023)."""

CO2E_PETROL_FACTOR: float = 0.20
"""kg CO₂e emitted per kilometre driven in a petrol passenger car."""

CO2E_LPG_FACTOR: float = 3.00
"""kg CO₂e emitted per kilogram of Liquefied Petroleum Gas combusted."""

CO2E_MEAT_MEAL_FACTOR: float = 2.50
"""kg CO₂e per heavy meat-based meal (beef/lamb/pork/poultry weighted average)."""

CO2E_PLANT_MEAL_FACTOR: float = 1.00
"""kg CO₂e per plant-based meal (vegetarian/vegan weighted average)."""

WEEKS_PER_MONTH: float = 4.33
"""ISO-calendar weeks-per-month average used to scale weekly meal counts."""

# ---------------------------------------------------------------------------
# Benchmark Constants (kg CO₂e / month)
# ---------------------------------------------------------------------------
GLOBAL_AVERAGE_MONTHLY_KG: float = 400.0
"""Global average individual carbon footprint per month (4.8 t/yr ÷ 12)."""

TARGET_MONTHLY_KG: float = 167.0
"""IPCC 1.5 °C budget per-person target per month (2.0 t/yr ÷ 12)."""

# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------
_ISO_DATE_RE: re.Pattern[str] = re.compile(r"^\d{4}-\d{2}-\d{2}$")
"""Compiled regular expression matching YYYY-MM-DD date strings exactly."""


# ---------------------------------------------------------------------------
# Database Helpers
# ---------------------------------------------------------------------------

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a configured SQLite connection and guarantee cleanup.

    The connection is configured with:
    - ``row_factory = sqlite3.Row`` for dict-like row access
    - WAL journal mode for better concurrent read throughput
    - Foreign-key enforcement enabled

    Yields:
        An open ``sqlite3.Connection`` instance.

    Raises:
        sqlite3.Error: If the connection cannot be established within the
            10-second timeout.
    """
    conn: sqlite3.Connection = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create the ``carbon_logs`` table and seed demo data if the DB is empty.

    This function is idempotent — calling it on an already-populated database
    is a no-op for both the schema creation and the seed step.

    Side Effects:
        - Creates the ``carbon_logs`` table if it does not exist.
        - Creates an index on ``timestamp`` if it does not exist.
        - Inserts 4 historical sample rows when the table is empty.
    """
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS carbon_logs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                electricity_kwh  REAL    NOT NULL CHECK(electricity_kwh  >= 0),
                petrol_km        REAL    NOT NULL CHECK(petrol_km        >= 0),
                lpg_kg           REAL    NOT NULL CHECK(lpg_kg           >= 0),
                meat_meals       INTEGER NOT NULL CHECK(meat_meals       >= 0),
                plant_meals      INTEGER NOT NULL CHECK(plant_meals      >= 0),
                electricity_co2e REAL    NOT NULL,
                petrol_co2e      REAL    NOT NULL,
                lpg_co2e         REAL    NOT NULL,
                diet_co2e        REAL    NOT NULL,
                total_co2e       REAL    NOT NULL,
                timestamp        TEXT    NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON carbon_logs (timestamp);"
        )
        conn.commit()

        row_count: int = conn.execute("SELECT COUNT(*) FROM carbon_logs").fetchone()[0]
        if row_count == 0:
            logger.info("Empty database detected — inserting 4 seed records.")
            _seed_sample_data(conn)


def _seed_sample_data(conn: sqlite3.Connection) -> None:
    """Insert 4 months of declining-footprint sample data into ``carbon_logs``.

    The samples demonstrate a positive (downward) emission trend, providing
    immediate visual value to first-time users of the historical trend chart.

    Args:
        conn: An open ``sqlite3.Connection`` with an active transaction.

    Note:
        This function commits the transaction before returning.
    """
    # (electricity_kwh, petrol_km, lpg_kg, meat_meals/wk, plant_meals/wk, timestamp)
    samples: list[tuple[float, float, float, int, int, str]] = [
        (450.0, 1200.0, 25.0, 15, 5,  "2026-02-15T12:00:00"),
        (380.0,  900.0, 20.0, 12, 8,  "2026-03-15T12:00:00"),
        (280.0,  600.0, 16.0,  9, 12, "2026-04-15T12:00:00"),
        (200.0,  450.0, 14.0,  7, 14, "2026-05-15T12:00:00"),
    ]
    for elec, petrol, lpg, meat, plant, ts in samples:
        e_co2 = elec   * CO2E_ELECTRICITY_FACTOR
        p_co2 = petrol * CO2E_PETROL_FACTOR
        l_co2 = lpg    * CO2E_LPG_FACTOR
        d_co2 = (
            (meat * CO2E_MEAT_MEAL_FACTOR) + (plant * CO2E_PLANT_MEAL_FACTOR)
        ) * WEEKS_PER_MONTH
        total = e_co2 + p_co2 + l_co2 + d_co2
        conn.execute(
            """
            INSERT INTO carbon_logs
                (electricity_kwh, petrol_km, lpg_kg, meat_meals, plant_meals,
                 electricity_co2e, petrol_co2e, lpg_co2e, diet_co2e, total_co2e, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (elec, petrol, lpg, meat, plant, e_co2, p_co2, l_co2, d_co2, total, ts),
        )
    conn.commit()
    logger.info("Seed data inserted successfully.")


# Boot-time DB initialisation
init_db()

# ---------------------------------------------------------------------------
# Pydantic Schema
# ---------------------------------------------------------------------------

class FootprintInput(BaseModel):
    """Validated consumption metrics submitted by the end-user.

    All numeric fields are validated at the Pydantic layer before any
    business logic runs, ensuring that only physically meaningful values
    ever reach the calculation and persistence layers.

    Attributes:
        electricity_kwh: Monthly electricity usage in kilowatt-hours (0–10 000).
        petrol_km: Monthly petrol vehicle distance in kilometres (0–50 000).
        lpg_kg: Monthly LPG cooking gas consumed in kilograms (0–500).
        meat_meals: Weekly meat-based meal count (0–63).
        plant_meals: Weekly plant-based meal count (0–63).
        date: Optional ISO-8601 log date (``YYYY-MM-DD``). Defaults to today.

    Example:
        >>> fp = FootprintInput(
        ...     electricity_kwh=150.0,
        ...     petrol_km=400.0,
        ...     lpg_kg=14.0,
        ...     meat_meals=7,
        ...     plant_meals=14,
        ... )
    """

    electricity_kwh: float = Field(
        ...,
        ge=0,
        le=10_000,
        description="Monthly electricity consumption in kWh (0–10 000).",
        examples=[150.0],
    )
    petrol_km: float = Field(
        ...,
        ge=0,
        le=50_000,
        description="Monthly petrol vehicle distance in km (0–50 000).",
        examples=[400.0],
    )
    lpg_kg: float = Field(
        ...,
        ge=0,
        le=500,
        description="Monthly LPG consumption in kg (0–500).",
        examples=[14.0],
    )
    meat_meals: int = Field(
        ...,
        ge=0,
        le=63,
        description="Heavy meat-based meals per week (0–63).",
        examples=[7],
    )
    plant_meals: int = Field(
        ...,
        ge=0,
        le=63,
        description="Plant-based meals per week (0–63).",
        examples=[14],
    )
    date: str | None = Field(
        default=None,
        description="ISO-8601 date (YYYY-MM-DD) for the log entry. Defaults to today.",
        examples=["2026-06-15"],
    )

    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        """Validate that ``date`` is either ``None`` or a valid ``YYYY-MM-DD`` string.

        Args:
            v: The raw value provided for the ``date`` field.

        Returns:
            ``None`` if the field was not supplied, otherwise the validated
            date string in ``YYYY-MM-DD`` format.

        Raises:
            ValueError: If ``v`` is non-None and does not match ``YYYY-MM-DD``
                format or is not a valid calendar date.
        """
        if v is None or v == "":
            return None
        if not isinstance(v, str) or not _ISO_DATE_RE.match(v):
            raise ValueError(
                f"Invalid date '{v}'. Expected ISO-8601 format YYYY-MM-DD "
                "(e.g. '2026-06-15')."
            )
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"'{v}' is not a valid calendar date.") from exc
        return v

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Emission Calculation — Pure Function (no I/O)
# ---------------------------------------------------------------------------

def _compute_emissions(data: FootprintInput) -> EmissionResult:
    """Compute a full emission breakdown and comparison from consumption data.

    This is a **pure function**: it performs no I/O and has no side effects.
    The same inputs will always produce the same outputs, making it fully
    unit-testable without database or network access.

    Args:
        data: A validated ``FootprintInput`` instance.

    Returns:
        A dictionary with three keys:

        - ``"breakdown"`` (``BreakdownDict``): Per-sector monthly emissions
          in kg CO₂e — keys ``electricity``, ``petrol``, ``lpg``, ``diet``.
        - ``"totals"`` (``TotalsDict``): Aggregate figures —
          ``monthly_kg``, ``annual_kg``, ``annual_tons``.
        - ``"comparisons"`` (``ComparisonsDict``): Contextual benchmarks —
          ``pct_of_global_avg``, ``pct_of_target``, ``highest_sector``,
          ``highest_emissions_kg``.

    Example:
        >>> from agent_core import FootprintInput, _compute_emissions
        >>> fp = FootprintInput(electricity_kwh=150, petrol_km=400,
        ...                     lpg_kg=14, meat_meals=7, plant_meals=14)
        >>> result = _compute_emissions(fp)
        >>> result["breakdown"]["electricity"]
        127.5
    """
    # Per-sector monthly emissions (kg CO₂e)
    elec_co2: float   = data.electricity_kwh * CO2E_ELECTRICITY_FACTOR
    petrol_co2: float = data.petrol_km       * CO2E_PETROL_FACTOR
    lpg_co2: float    = data.lpg_kg          * CO2E_LPG_FACTOR
    diet_co2: float   = (
        (data.meat_meals  * CO2E_MEAT_MEAL_FACTOR)
        + (data.plant_meals * CO2E_PLANT_MEAL_FACTOR)
    ) * WEEKS_PER_MONTH

    # Aggregate totals. Response totals are derived from the same rounded
    # monthly value so API consumers can reproduce annual figures exactly.
    monthly_kg: float = elec_co2 + petrol_co2 + lpg_co2 + diet_co2
    monthly_kg_response: float = round(monthly_kg, 2)
    annual_kg_response: float = round(monthly_kg_response * 12, 2)
    annual_tons_response: float = round(annual_kg_response / 1_000.0, 2)

    # Sector ranking
    sectors: dict[str, float] = {
        "Energy (Electricity)":            elec_co2,
        "Transportation (Petrol Vehicle)": petrol_co2,
        "Cooking Gas (LPG)":               lpg_co2,
        "Dietary Footprint":               diet_co2,
    }
    highest_sector: str   = max(sectors, key=sectors.get)  # type: ignore[arg-type]
    highest_val: float    = sectors[highest_sector]

    # Benchmark comparisons (guard against zero-division)
    pct_of_global_avg: float = (
        (monthly_kg / GLOBAL_AVERAGE_MONTHLY_KG) * 100
        if GLOBAL_AVERAGE_MONTHLY_KG > 0 else 0.0
    )
    pct_of_target: float = (
        (monthly_kg / TARGET_MONTHLY_KG) * 100
        if TARGET_MONTHLY_KG > 0 else 0.0
    )

    return {
        "breakdown": {
            "electricity": round(elec_co2,   2),
            "petrol":      round(petrol_co2, 2),
            "lpg":         round(lpg_co2,    2),
            "diet":        round(diet_co2,   2),
        },
        "totals": {
            "monthly_kg":  monthly_kg_response,
            "annual_kg":   annual_kg_response,
            "annual_tons": annual_tons_response,
        },
        "comparisons": {
            "pct_of_global_avg":    round(pct_of_global_avg, 1),
            "pct_of_target":        round(pct_of_target,     1),
            "highest_sector":       highest_sector,
            "highest_emissions_kg": round(highest_val,       2),
        },
    }


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/calculate",
    summary="Calculate carbon emissions",
    tags=["Emissions"],
    response_description="Emission breakdown, annual totals, and benchmarks.",
)
def calculate_emissions(data: FootprintInput) -> EmissionResult:
    """Accept monthly consumption metrics and return a real-time emissions analysis.

    This endpoint is **read-only** — no data is persisted. Use ``/api/logs``
    to save an entry to the history database.

    Args:
        data: Validated consumption metrics from the request body.

    Returns:
        A JSON object with ``breakdown``, ``totals``, and ``comparisons`` keys.

    Raises:
        HTTPException: 422 if any field fails Pydantic validation.
    """
    logger.info(
        "Calculate request — elec=%.1f kWh, petrol=%.1f km, "
        "lpg=%.1f kg, meat=%d, plant=%d",
        data.electricity_kwh, data.petrol_km, data.lpg_kg,
        data.meat_meals, data.plant_meals,
    )
    return _compute_emissions(data)


@app.post(
    "/api/logs",
    summary="Save a carbon log entry",
    tags=["History"],
    response_description="Confirmation with the calculated emission data.",
    status_code=200,
)
def save_log(data: FootprintInput) -> dict[str, Any]:
    """Calculate emissions for the supplied metrics and persist the result.

    The entry is stored with an ISO-8601 timestamp. If ``data.date`` is
    provided it is used; otherwise the current UTC datetime is used.

    Args:
        data: Validated consumption metrics including an optional log date.

    Returns:
        A JSON object with ``status``, ``message``, and ``data`` (the full
        emission result for the saved entry).

    Raises:
        HTTPException: 422 if validation fails; 500 if the DB write fails.
    """
    calc: EmissionResult = _compute_emissions(data)
    ts_str: str = (data.date + "T12:00:00") if data.date else datetime.now().isoformat()

    try:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO carbon_logs
                    (electricity_kwh, petrol_km, lpg_kg, meat_meals, plant_meals,
                     electricity_co2e, petrol_co2e, lpg_co2e, diet_co2e, total_co2e, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.electricity_kwh, data.petrol_km, data.lpg_kg,
                    data.meat_meals, data.plant_meals,
                    calc["breakdown"]["electricity"],
                    calc["breakdown"]["petrol"],
                    calc["breakdown"]["lpg"],
                    calc["breakdown"]["diet"],
                    calc["totals"]["monthly_kg"],
                    ts_str,
                ),
            )
            conn.commit()
        logger.info(
            "Log saved — date=%s, total=%.2f kg CO₂e",
            ts_str, calc["totals"]["monthly_kg"],
        )
    except sqlite3.Error as exc:
        logger.error("Database write error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to persist the log entry. Please try again.",
        ) from exc

    return {
        "status":  "success",
        "message": "Consumption metrics successfully logged.",
        "data":    calc,
    }


@app.get(
    "/api/history",
    summary="Retrieve emission history",
    tags=["History"],
    response_description="List of up to 15 log entries sorted oldest-first.",
)
def get_logs_history() -> list[HistoryEntry]:
    """Return the 15 most recent carbon log entries sorted chronologically.

    Entries are ordered oldest-first so that clients can render a left-to-right
    trend chart without additional sorting.

    Returns:
        A JSON array of history entry objects, each containing ``id``, ``date``,
        ``total_co2e``, ``breakdown``, and the original input fields.

    Raises:
        HTTPException: 500 if the database query fails.
    """
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, electricity_kwh, petrol_km, lpg_kg, meat_meals, plant_meals,
                       electricity_co2e, petrol_co2e, lpg_co2e, diet_co2e, total_co2e, timestamp
                FROM (
                    SELECT id, electricity_kwh, petrol_km, lpg_kg, meat_meals, plant_meals,
                           electricity_co2e, petrol_co2e, lpg_co2e, diet_co2e, total_co2e, timestamp
                    FROM   carbon_logs
                    ORDER  BY timestamp DESC
                    LIMIT  15
                )
                ORDER BY timestamp ASC
                """
            ).fetchall()
    except sqlite3.Error as exc:
        logger.error("Database read error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve history. Please try again.",
        ) from exc

    return [
        {
            "id":              row["id"],
            "electricity_kwh": row["electricity_kwh"],
            "petrol_km":       row["petrol_km"],
            "lpg_kg":          row["lpg_kg"],
            "meat_meals":      row["meat_meals"],
            "plant_meals":     row["plant_meals"],
            "breakdown": {
                "electricity": row["electricity_co2e"],
                "petrol":      row["petrol_co2e"],
                "lpg":         row["lpg_co2e"],
                "diet":        row["diet_co2e"],
            },
            "total_co2e": row["total_co2e"],
            "date": (
                row["timestamp"].split("T")[0]
                if "T" in row["timestamp"]
                else row["timestamp"]
            ),
        }
        for row in rows
    ]


@app.post(
    "/api/reset",
    summary="Clear all history",
    tags=["History"],
    response_description="Confirmation that all records were deleted.",
)
def reset_history() -> dict[str, str]:
    """Permanently delete all carbon log entries from the database.

    This action is **irreversible**. It is intended for development and
    demonstration purposes; a production deployment would require
    authentication before allowing this operation.

    Returns:
        A JSON object with ``status = "success"`` and a confirmation message.

    Raises:
        HTTPException: 500 if the database delete fails.
    """
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM carbon_logs")
            conn.commit()
        logger.warning("History reset — all carbon_logs records deleted.")
    except sqlite3.Error as exc:
        logger.error("Database delete error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to reset history. Please try again.",
        ) from exc

    return {"status": "success", "message": "History logs successfully cleared."}


# ---------------------------------------------------------------------------
# Health Check Endpoint
# ---------------------------------------------------------------------------

@app.get(
    "/api/health",
    summary="Service health check",
    tags=["Monitoring"],
    response_description="Service status, database connectivity, and API version.",
)
def health_check() -> dict[str, str]:
    """Return the current health status of the service.

    Performs a lightweight ``SELECT 1`` probe against the SQLite database
    to verify connectivity. This endpoint is used by the Docker HEALTHCHECK
    directive and by uptime-monitoring services.

    Returns:
        A JSON object with:

        - ``status``: ``"ok"`` if the service is healthy.
        - ``database``: ``"ok"`` if the database is reachable, ``"degraded"``
          otherwise.
        - ``version``: The current API version string.
    """
    try:
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
        db_status = "ok"
    except sqlite3.Error as exc:
        logger.error("Health check — database probe failed: %s", exc)
        db_status = "degraded"

    return {
        "status":   "ok",
        "database": db_status,
        "version":  "2.0.0",
    }


# ---------------------------------------------------------------------------
# Static File Routes
# ---------------------------------------------------------------------------
_STATIC_CACHE: str = "public, max-age=3600, stale-while-revalidate=86400"
_NO_CACHE: str     = "no-cache, no-store, must-revalidate"


@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    """Serve the main AURA Carbon dashboard HTML page.

    Returns:
        A ``FileResponse`` for ``index.html`` with no-cache headers to ensure
        clients always receive the latest markup.
    """
    return FileResponse("index.html", headers={"Cache-Control": _NO_CACHE})


@app.get("/style.css", include_in_schema=False)
def serve_style() -> FileResponse:
    """Serve the application stylesheet.

    Returns:
        A ``FileResponse`` for ``style.css`` with a 1-hour browser cache.
    """
    return FileResponse(
        "style.css",
        media_type="text/css",
        headers={"Cache-Control": _STATIC_CACHE},
    )


@app.get("/app.js", include_in_schema=False)
def serve_app() -> FileResponse:
    """Serve the application JavaScript bundle.

    Returns:
        A ``FileResponse`` for ``app.js`` with a 1-hour browser cache.
    """
    return FileResponse(
        "app.js",
        media_type="application/javascript",
        headers={"Cache-Control": _STATIC_CACHE},
    )
