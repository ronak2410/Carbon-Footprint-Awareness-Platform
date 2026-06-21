"""
AURA Carbon Footprint Analytics Platform — API Core
=====================================================
FastAPI backend handling emission calculations, persistent logging,
history retrieval, and static-file serving.

Design principles applied:
- Full type annotations throughout (PEP 484)
- Pydantic v2 field validators for input sanitisation
- Structured logging via stdlib `logging`
- Explicit HTTP security response headers on every route
- Parameterised SQL queries only (no string interpolation)
- Context-manager-based DB connections (no leaked handles)
- ISO-date validation for custom log dates
- Centralised emission-factor constants
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Generator, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("aura_carbon")

# ---------------------------------------------------------------------------
# Application Setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AURA Carbon Analytics API",
    description=(
        "REST API powering the AURA Carbon Footprint Awareness Platform. "
        "Provides real-time emission calculations, persistent logging, "
        "history retrieval, and data export endpoints."
    ),
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Narrow CORS: only the Hugging Face Space origin and localhost for development
ALLOWED_ORIGINS: list[str] = [
    "https://ronak2410-carbon-footprint-dashboard.hf.space",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
    max_age=600,
)

# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    ),
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next: Any) -> Response:
    """Attach security headers to every HTTP response."""
    response: Response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response


# ---------------------------------------------------------------------------
# Database Configuration
# ---------------------------------------------------------------------------
DB_PATH: str = os.environ.get("DB_PATH", "friday_carbon.db")

# Emission Reference Constants (IPCC / IEA values)
CO2E_ELECTRICITY_FACTOR: float = 0.85   # kg CO₂e per kWh  (India grid avg)
CO2E_PETROL_FACTOR: float = 0.20        # kg CO₂e per km   (petrol passenger car)
CO2E_LPG_FACTOR: float = 3.00           # kg CO₂e per kg   (LPG combustion)
CO2E_MEAT_MEAL_FACTOR: float = 2.50     # kg CO₂e per meal (mixed meat)
CO2E_PLANT_MEAL_FACTOR: float = 1.00    # kg CO₂e per meal (plant-based avg)
WEEKS_PER_MONTH: float = 4.33           # ISO calendar weeks-per-month average

# Benchmark references (kg CO₂e / month)
GLOBAL_AVERAGE_MONTHLY_KG: float = 400.0   # 4.8 t/yr ÷ 12
TARGET_MONTHLY_KG: float = 167.0           # IPCC 1.5 °C target: 2 t/yr ÷ 12

# ---------------------------------------------------------------------------
# Database Helpers
# ---------------------------------------------------------------------------
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection that is always closed on exit."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")   # Better concurrent read performance
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """
    Create the carbon_logs table if absent, and seed 4 historical sample
    records that demonstrate a positive (declining) emission trend.
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

        count: int = conn.execute("SELECT COUNT(*) FROM carbon_logs").fetchone()[0]
        if count == 0:
            logger.info("Empty database — seeding with 4 sample historical records.")
            _seed_sample_data(conn)


def _seed_sample_data(conn: sqlite3.Connection) -> None:
    """Insert 4 months of declining-footprint demonstration data."""
    samples = [
        (450.0, 1200.0, 25.0, 15, 5,  "2026-02-15T12:00:00"),
        (380.0,  900.0, 20.0, 12, 8,  "2026-03-15T12:00:00"),
        (280.0,  600.0, 16.0,  9, 12, "2026-04-15T12:00:00"),
        (200.0,  450.0, 14.0,  7, 14, "2026-05-15T12:00:00"),
    ]
    for elec, petrol, lpg, meat, plant, ts in samples:
        e_co2  = elec   * CO2E_ELECTRICITY_FACTOR
        p_co2  = petrol * CO2E_PETROL_FACTOR
        l_co2  = lpg    * CO2E_LPG_FACTOR
        d_co2  = ((meat * CO2E_MEAT_MEAL_FACTOR) + (plant * CO2E_PLANT_MEAL_FACTOR)) * WEEKS_PER_MONTH
        total  = e_co2 + p_co2 + l_co2 + d_co2
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


# Boot-time DB initialisation
init_db()

# ---------------------------------------------------------------------------
# Pydantic Schema
# ---------------------------------------------------------------------------

class FootprintInput(BaseModel):
    """Validated consumption metrics submitted by the user."""

    electricity_kwh: float = Field(
        ..., ge=0, le=10_000,
        description="Monthly electricity consumption in kWh (0–10 000).",
    )
    petrol_km: float = Field(
        ..., ge=0, le=50_000,
        description="Monthly petrol vehicle distance in km (0–50 000).",
    )
    lpg_kg: float = Field(
        ..., ge=0, le=500,
        description="Monthly LPG consumption in kg (0–500).",
    )
    meat_meals: int = Field(
        ..., ge=0, le=63,
        description="Meat-based meals per week (0–63, i.e. up to 3 per day).",
    )
    plant_meals: int = Field(
        ..., ge=0, le=63,
        description="Plant-based meals per week (0–63).",
    )
    date: Optional[str] = Field(
        default=None,
        description="ISO-8601 date (YYYY-MM-DD) for the log entry. Defaults to today.",
    )

    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        """Accept None or a valid YYYY-MM-DD date string; reject anything else."""
        if v is None or v == "":
            return None
        if not isinstance(v, str) or not _ISO_DATE_RE.match(v):
            raise ValueError(
                f"Invalid date '{v}'. Expected ISO-8601 format YYYY-MM-DD."
            )
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError(f"Date '{v}' is not a valid calendar date.")
        return v

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Emission Calculation Helper
# ---------------------------------------------------------------------------

def _compute_emissions(data: FootprintInput) -> dict[str, Any]:
    """
    Pure calculation function — no side effects.

    Returns a structured dict with breakdown, totals, and comparison data.
    """
    elec_co2   = data.electricity_kwh * CO2E_ELECTRICITY_FACTOR
    petrol_co2 = data.petrol_km       * CO2E_PETROL_FACTOR
    lpg_co2    = data.lpg_kg          * CO2E_LPG_FACTOR
    diet_co2   = (
        (data.meat_meals  * CO2E_MEAT_MEAL_FACTOR)
        + (data.plant_meals * CO2E_PLANT_MEAL_FACTOR)
    ) * WEEKS_PER_MONTH

    monthly_kg  = elec_co2 + petrol_co2 + lpg_co2 + diet_co2
    annual_kg   = monthly_kg * 12
    annual_tons = annual_kg / 1_000.0

    sectors: dict[str, float] = {
        "Energy (Electricity)":           elec_co2,
        "Transportation (Petrol Vehicle)": petrol_co2,
        "Cooking Gas (LPG)":              lpg_co2,
        "Dietary Footprint":              diet_co2,
    }
    highest_sector = max(sectors, key=sectors.get)
    highest_val    = sectors[highest_sector]

    pct_of_global_avg = (
        (monthly_kg / GLOBAL_AVERAGE_MONTHLY_KG) * 100
        if GLOBAL_AVERAGE_MONTHLY_KG > 0 else 0.0
    )
    pct_of_target = (
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
            "monthly_kg":  round(monthly_kg,  2),
            "annual_kg":   round(annual_kg,   2),
            "annual_tons": round(annual_tons, 2),
        },
        "comparisons": {
            "pct_of_global_avg":      round(pct_of_global_avg, 1),
            "pct_of_target":          round(pct_of_target,     1),
            "highest_sector":         highest_sector,
            "highest_emissions_kg":   round(highest_val,       2),
        },
    }


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/calculate", summary="Calculate carbon emissions", tags=["Emissions"])
def calculate_emissions(data: FootprintInput) -> dict[str, Any]:
    """
    Accept monthly consumption metrics and return a real-time emissions
    breakdown, annual projections, and benchmarks.

    No data is persisted by this endpoint.
    """
    logger.info(
        "Calculating emissions — elec=%.1f kWh, petrol=%.1f km, "
        "lpg=%.1f kg, meat=%d, plant=%d",
        data.electricity_kwh, data.petrol_km, data.lpg_kg,
        data.meat_meals, data.plant_meals,
    )
    return _compute_emissions(data)


@app.post("/api/logs", summary="Log consumption entry", tags=["History"])
def save_log(data: FootprintInput) -> dict[str, Any]:
    """
    Calculate emissions for the given consumption metrics and persist the
    result as a dated entry in the SQLite history database.
    """
    calc   = _compute_emissions(data)
    ts_str = (data.date + "T12:00:00") if data.date else datetime.now().isoformat()

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
        logger.info("Saved log entry dated %s — total %.2f kg CO₂e", ts_str, calc["totals"]["monthly_kg"])
    except sqlite3.Error as exc:
        logger.error("Database error saving log: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to persist log entry.") from exc

    return {
        "status":  "success",
        "message": "Consumption metrics successfully logged.",
        "data":    calc,
    }


@app.get("/api/history", summary="Retrieve emission history", tags=["History"])
def get_logs_history() -> list[dict[str, Any]]:
    """
    Return the 15 most recent carbon log entries sorted chronologically
    (oldest → newest) for trend-chart rendering.
    """
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, electricity_kwh, petrol_km, lpg_kg, meat_meals, plant_meals,
                       electricity_co2e, petrol_co2e, lpg_co2e, diet_co2e, total_co2e, timestamp
                FROM carbon_logs
                ORDER BY timestamp ASC
                LIMIT 15
                """
            ).fetchall()
    except sqlite3.Error as exc:
        logger.error("Database error fetching history: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve history.") from exc

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
            "date": row["timestamp"].split("T")[0] if "T" in row["timestamp"] else row["timestamp"],
        }
        for row in rows
    ]


@app.post("/api/reset", summary="Clear all history", tags=["History"])
def reset_history() -> dict[str, str]:
    """
    Permanently delete all carbon log entries from the database.
    This action is irreversible.
    """
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM carbon_logs")
            conn.commit()
        logger.warning("History reset — all carbon_logs records deleted.")
    except sqlite3.Error as exc:
        logger.error("Database error during reset: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to reset history.") from exc

    return {"status": "success", "message": "History logs successfully cleared."}


# ---------------------------------------------------------------------------
# Health Check Endpoint
# ---------------------------------------------------------------------------

@app.get("/api/health", summary="Service health check", tags=["Monitoring"])
def health_check() -> dict[str, str]:
    """Returns a 200 OK with service status for uptime monitoring."""
    try:
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
        db_status = "ok"
    except sqlite3.Error:
        db_status = "degraded"

    return {
        "status":   "ok",
        "database": db_status,
        "version":  "2.0.0",
    }


# ---------------------------------------------------------------------------
# Static File Routes
# ---------------------------------------------------------------------------
_STATIC_CACHE = "public, max-age=3600, stale-while-revalidate=86400"
_NO_CACHE      = "no-cache, no-store, must-revalidate"


@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    """Serve the main dashboard HTML page."""
    return FileResponse("index.html", headers={"Cache-Control": _NO_CACHE})


@app.get("/style.css", include_in_schema=False)
def serve_style() -> FileResponse:
    """Serve application stylesheet."""
    return FileResponse(
        "style.css",
        media_type="text/css",
        headers={"Cache-Control": _STATIC_CACHE},
    )


@app.get("/app.js", include_in_schema=False)
def serve_app() -> FileResponse:
    """Serve application JavaScript bundle."""
    return FileResponse(
        "app.js",
        media_type="application/javascript",
        headers={"Cache-Control": _STATIC_CACHE},
    )
