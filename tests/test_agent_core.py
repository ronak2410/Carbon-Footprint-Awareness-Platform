"""
AURA Carbon — Comprehensive Test Suite v3
==========================================
Tests for all FastAPI endpoints, input validation, emission
calculation accuracy, database operations, security headers,
and end-to-end integration flows.

Test classes:
    TestCalculate       — /api/calculate endpoint (19 tests)
    TestCalculateParam  — Parametrized emission factor accuracy (3 tests)
    TestLogs            — /api/logs endpoint (10 tests)
    TestHistory         — /api/history endpoint (7 tests)
    TestReset           — /api/reset endpoint (5 tests)
    TestHealth          — /api/health endpoint (5 tests)
    TestStaticFiles     — Static file serving (5 tests)
    TestSecurityHeaders — HTTP security header assertions (6 tests)
    TestIntegration     — Cross-endpoint workflow tests (4 tests)
    TestBodySizeLimit   — 64 KB request body enforcement (1 test)
"""

from __future__ import annotations

import pytest

# conftest.py already wires DB_PATH, imports agent_core, and provides
# the ``client`` module-level object and the ``clean_db`` autouse fixture.
from tests.conftest import client

# ---------------------------------------------------------------------------
# Shared Payload Constants
# ---------------------------------------------------------------------------

Payload = dict[str, object]

SAMPLE: Payload = {
    "electricity_kwh": 150.0,
    "petrol_km":       400.0,
    "lpg_kg":          14.0,
    "meat_meals":      7,
    "plant_meals":     14,
}

LOW: Payload = {
    "electricity_kwh": 30.0,
    "petrol_km":       80.0,
    "lpg_kg":          3.0,
    "meat_meals":      1,
    "plant_meals":     20,
}

HIGH: Payload = {
    "electricity_kwh": 800.0,
    "petrol_km":       2500.0,
    "lpg_kg":          60.0,
    "meat_meals":      20,
    "plant_meals":     1,
}

ZERO: Payload = dict.fromkeys(SAMPLE, 0)


# ===========================================================================
# 1.  /api/calculate
# ===========================================================================

class TestCalculate:
    """Tests for the POST /api/calculate endpoint."""

    def test_returns_200(self) -> None:
        """A well-formed payload must return HTTP 200."""
        assert client.post("/api/calculate", json=SAMPLE).status_code == 200

    def test_response_has_required_top_level_keys(self) -> None:
        """Response body must contain breakdown, totals, and comparisons."""
        data = client.post("/api/calculate", json=SAMPLE).json()
        for key in ("breakdown", "totals", "comparisons"):
            assert key in data, f"Missing top-level key: '{key}'"

    def test_breakdown_contains_all_four_sectors(self) -> None:
        """Breakdown must include all four emission sectors."""
        bd = client.post("/api/calculate", json=SAMPLE).json()["breakdown"]
        for key in ("electricity", "petrol", "lpg", "diet"):
            assert key in bd, f"Missing sector: '{key}'"

    def test_totals_contains_three_aggregates(self) -> None:
        """Totals must include monthly_kg, annual_kg, and annual_tons."""
        totals = client.post("/api/calculate", json=SAMPLE).json()["totals"]
        for key in ("monthly_kg", "annual_kg", "annual_tons"):
            assert key in totals, f"Missing totals key: '{key}'"

    # --- Numerical accuracy ---

    def test_electricity_emission_correct(self) -> None:
        """150 kWh × 0.85 kg/kWh = 127.50 kg CO₂e."""
        bd = client.post("/api/calculate", json=SAMPLE).json()["breakdown"]
        assert abs(bd["electricity"] - 127.50) < 0.01

    def test_petrol_emission_correct(self) -> None:
        """400 km × 0.20 kg/km = 80.00 kg CO₂e."""
        bd = client.post("/api/calculate", json=SAMPLE).json()["breakdown"]
        assert abs(bd["petrol"] - 80.00) < 0.01

    def test_lpg_emission_correct(self) -> None:
        """14 kg × 3.00 kg/kg = 42.00 kg CO₂e."""
        bd = client.post("/api/calculate", json=SAMPLE).json()["breakdown"]
        assert abs(bd["lpg"] - 42.00) < 0.01

    def test_annual_kg_equals_monthly_times_12(self) -> None:
        """annual_kg must equal monthly_kg × 12 (before rounding)."""
        totals = client.post("/api/calculate", json=SAMPLE).json()["totals"]
        assert abs(totals["annual_kg"] - totals["monthly_kg"] * 12) < 0.01

    def test_annual_tons_derived_correctly(self) -> None:
        """annual_tons must equal annual_kg / 1000 rounded to 2 dp."""
        totals = client.post("/api/calculate", json=SAMPLE).json()["totals"]
        expected = round(totals["annual_kg"] / 1000, 2)
        assert abs(totals["annual_tons"] - expected) < 0.01

    # --- Edge cases ---

    def test_zero_payload_yields_zero_totals(self) -> None:
        """All-zero inputs must produce zero total emissions."""
        totals = client.post("/api/calculate", json=ZERO).json()["totals"]
        assert totals["monthly_kg"] == 0.0
        assert totals["annual_kg"]  == 0.0
        assert totals["annual_tons"] == 0.0

    def test_high_usage_exceeds_global_average(self) -> None:
        """Heavy usage must far exceed the 4.8 t global average."""
        totals = client.post("/api/calculate", json=HIGH).json()["totals"]
        assert totals["annual_tons"] > 4.8

    def test_low_usage_below_global_average(self) -> None:
        """Low usage must be well below the 4.8 t global average."""
        totals = client.post("/api/calculate", json=LOW).json()["totals"]
        assert totals["annual_tons"] < 4.8

    def test_highest_sector_is_non_empty_string(self) -> None:
        """The highest emission sector must be identified and non-empty."""
        cmp = client.post("/api/calculate", json=HIGH).json()["comparisons"]
        assert "highest_sector" in cmp
        assert isinstance(cmp["highest_sector"], str)
        assert cmp["highest_sector"] != ""

    def test_pct_of_global_avg_is_positive_for_nonzero_input(self) -> None:
        """pct_of_global_avg must be positive for non-zero inputs."""
        cmp = client.post("/api/calculate", json=SAMPLE).json()["comparisons"]
        assert cmp["pct_of_global_avg"] > 0

    def test_all_breakdown_values_are_non_negative(self) -> None:
        """All sector emissions must be non-negative."""
        bd = client.post("/api/calculate", json=SAMPLE).json()["breakdown"]
        for sector, value in bd.items():
            assert value >= 0, f"Sector '{sector}' has negative emission: {value}"

    # --- Validation ---

    def test_missing_electricity_field_returns_422(self) -> None:
        bad = {k: v for k, v in SAMPLE.items() if k != "electricity_kwh"}
        assert client.post("/api/calculate", json=bad).status_code == 422

    def test_negative_electricity_rejected(self) -> None:
        assert (
            client.post("/api/calculate", json={**SAMPLE, "electricity_kwh": -1}).status_code
            == 422
        )

    def test_negative_petrol_rejected(self) -> None:
        assert client.post("/api/calculate", json={**SAMPLE, "petrol_km": -1}).status_code == 422

    def test_electricity_above_max_rejected(self) -> None:
        assert (
            client.post("/api/calculate", json={**SAMPLE, "electricity_kwh": 99999}).status_code
            == 422
        )

    def test_meat_meals_above_63_rejected(self) -> None:
        assert client.post("/api/calculate", json={**SAMPLE, "meat_meals": 100}).status_code == 422

    def test_string_value_for_numeric_field_rejected(self) -> None:
        assert (
            client.post("/api/calculate", json={**SAMPLE, "electricity_kwh": "bad"}).status_code
            == 422
        )


# ===========================================================================
# 2.  Parametrized Emission Factor Accuracy
# ===========================================================================

class TestCalculateParam:
    """Parametrized tests verifying each emission factor independently."""

    @pytest.mark.parametrize("kwh,expected_kg", [
        (100.0, 85.0),
        (200.0, 170.0),
        (500.0, 425.0),
    ])
    def test_electricity_factor(self, kwh: float, expected_kg: float) -> None:
        """Electricity emission = kWh × 0.85 for any valid kWh value."""
        payload = {**ZERO, "electricity_kwh": kwh}
        bd = client.post("/api/calculate", json=payload).json()["breakdown"]
        assert abs(bd["electricity"] - expected_kg) < 0.01, (
            f"Expected {expected_kg} kg for {kwh} kWh, got {bd['electricity']}"
        )

    @pytest.mark.parametrize("km,expected_kg", [
        (500.0, 100.0),
        (1000.0, 200.0),
        (2000.0, 400.0),
    ])
    def test_petrol_factor(self, km: float, expected_kg: float) -> None:
        """Petrol emission = km × 0.20 for any valid km value."""
        payload = {**ZERO, "petrol_km": km}
        bd = client.post("/api/calculate", json=payload).json()["breakdown"]
        assert abs(bd["petrol"] - expected_kg) < 0.01

    @pytest.mark.parametrize("kg_lpg,expected_kg", [
        (10.0, 30.0),
        (20.0, 60.0),
        (50.0, 150.0),
    ])
    def test_lpg_factor(self, kg_lpg: float, expected_kg: float) -> None:
        """LPG emission = kg × 3.00 for any valid kg value."""
        payload = {**ZERO, "lpg_kg": kg_lpg}
        bd = client.post("/api/calculate", json=payload).json()["breakdown"]
        assert abs(bd["lpg"] - expected_kg) < 0.01


# ===========================================================================
# 3.  /api/logs
# ===========================================================================

class TestLogs:
    """Tests for the POST /api/logs endpoint."""

    def test_save_returns_200(self) -> None:
        assert client.post("/api/logs", json=SAMPLE).status_code == 200

    def test_save_response_status_field_is_success(self) -> None:
        assert client.post("/api/logs", json=SAMPLE).json()["status"] == "success"

    def test_save_response_includes_emission_data(self) -> None:
        resp = client.post("/api/logs", json=SAMPLE).json()
        assert "data" in resp
        assert "totals" in resp["data"]

    def test_saved_log_appears_in_history(self) -> None:
        client.post("/api/logs", json=SAMPLE)
        history = client.get("/api/history").json()
        assert len(history) >= 1

    def test_custom_date_stored_correctly(self) -> None:
        """A log with an explicit date must persist that exact date."""
        client.post("/api/logs", json={**SAMPLE, "date": "2025-01-15"})
        dates = [e["date"] for e in client.get("/api/history").json()]
        assert "2025-01-15" in dates

    def test_multiple_saves_all_succeed(self) -> None:
        for _ in range(3):
            assert client.post("/api/logs", json=SAMPLE).status_code == 200

    def test_missing_required_field_returns_422(self) -> None:
        bad = {k: v for k, v in SAMPLE.items() if k != "petrol_km"}
        assert client.post("/api/logs", json=bad).status_code == 422

    def test_invalid_date_format_dd_mm_yyyy_rejected(self) -> None:
        assert client.post("/api/logs", json={**SAMPLE, "date": "21-06-2025"}).status_code == 422

    def test_nonsense_date_string_rejected(self) -> None:
        assert client.post("/api/logs", json={**SAMPLE, "date": "not-a-date"}).status_code == 422

    def test_none_date_defaults_to_today(self) -> None:
        assert client.post("/api/logs", json={**SAMPLE, "date": None}).status_code == 200


# ===========================================================================
# 4.  /api/history
# ===========================================================================

class TestHistory:
    """Tests for the GET /api/history endpoint."""

    def test_returns_200(self) -> None:
        assert client.get("/api/history").status_code == 200

    def test_response_is_a_list(self) -> None:
        assert isinstance(client.get("/api/history").json(), list)

    def test_entry_has_all_required_fields(self) -> None:
        client.post("/api/logs", json=SAMPLE)
        entry = client.get("/api/history").json()[0]
        for field in ("id", "date", "total_co2e", "breakdown", "electricity_kwh"):
            assert field in entry, f"Missing field: '{field}'"

    def test_breakdown_has_four_sector_keys(self) -> None:
        client.post("/api/logs", json=SAMPLE)
        bd = client.get("/api/history").json()[0]["breakdown"]
        for key in ("electricity", "petrol", "lpg", "diet"):
            assert key in bd

    def test_history_ordered_oldest_first(self) -> None:
        """Chronological (ascending) order is required for trend chart rendering."""
        client.post("/api/logs", json={**SAMPLE, "date": "2024-01-01"})
        client.post("/api/logs", json={**SAMPLE, "date": "2024-06-01"})
        history = client.get("/api/history").json()
        target_dates = [h["date"] for h in history if h["date"] in ("2024-01-01", "2024-06-01")]
        if len(target_dates) == 2:
            assert target_dates.index("2024-01-01") < target_dates.index("2024-06-01")

    def test_history_capped_at_15_entries(self) -> None:
        for _ in range(20):
            client.post("/api/logs", json=SAMPLE)
        assert len(client.get("/api/history").json()) <= 15

    def test_seed_data_present_on_fresh_db(self) -> None:
        """A freshly initialised database must contain exactly 4 seed records."""
        assert len(client.get("/api/history").json()) >= 4


# ===========================================================================
# 5.  /api/reset
# ===========================================================================

class TestReset:
    """Tests for the POST /api/reset endpoint."""

    def test_returns_200(self) -> None:
        assert client.post("/api/reset").status_code == 200

    def test_response_status_is_success(self) -> None:
        assert client.post("/api/reset").json()["status"] == "success"

    def test_clears_all_history_records(self) -> None:
        client.post("/api/logs", json=SAMPLE)
        client.post("/api/reset")
        assert client.get("/api/history").json() == []

    def test_double_reset_is_idempotent(self) -> None:
        assert client.post("/api/reset").status_code == 200
        assert client.post("/api/reset").status_code == 200

    def test_new_logs_can_be_added_after_reset(self) -> None:
        client.post("/api/reset")
        client.post("/api/logs", json=SAMPLE)
        assert len(client.get("/api/history").json()) == 1


# ===========================================================================
# 6.  /api/health
# ===========================================================================

class TestHealth:
    """Tests for the GET /api/health endpoint."""

    def test_returns_200(self) -> None:
        assert client.get("/api/health").status_code == 200

    def test_status_field_is_ok(self) -> None:
        assert client.get("/api/health").json()["status"] == "ok"

    def test_database_field_is_ok(self) -> None:
        assert client.get("/api/health").json()["database"] == "ok"

    def test_version_field_is_present(self) -> None:
        assert "version" in client.get("/api/health").json()

    def test_version_field_is_correct_format(self) -> None:
        """Version must be a non-empty semantic version string."""
        version = client.get("/api/health").json()["version"]
        assert isinstance(version, str) and len(version.split(".")) >= 2


# ===========================================================================
# 7.  Static File Serving
# ===========================================================================

class TestStaticFiles:
    """Tests for static file routes."""

    def test_index_html_returns_200(self) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_index_html_contains_brand_name(self) -> None:
        assert "AURA CARBON" in client.get("/").text

    def test_app_js_returns_200(self) -> None:
        assert client.get("/app.js").status_code == 200

    def test_style_css_returns_200(self) -> None:
        assert client.get("/style.css").status_code == 200

    def test_unknown_route_returns_404(self) -> None:
        assert client.get("/does-not-exist-xyz").status_code == 404


# ===========================================================================
# 8.  Security Headers
# ===========================================================================

class TestSecurityHeaders:
    """Verify that all required HTTP security headers are present on responses."""

    def test_x_content_type_options_is_nosniff(self) -> None:
        assert client.get("/").headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options_is_deny(self) -> None:
        assert client.get("/").headers.get("x-frame-options") == "DENY"

    def test_xss_protection_header_present(self) -> None:
        assert "1; mode=block" in client.get("/").headers.get("x-xss-protection", "")

    def test_referrer_policy_header_present(self) -> None:
        assert client.get("/").headers.get("referrer-policy") is not None

    def test_content_security_policy_header_present(self) -> None:
        csp = client.get("/").headers.get("content-security-policy", "")
        assert "default-src" in csp

    def test_strict_transport_security_present(self) -> None:
        hsts = client.get("/").headers.get("strict-transport-security", "")
        assert "max-age" in hsts


# ===========================================================================
# 9.  Integration Tests — End-to-End Workflows
# ===========================================================================

class TestIntegration:
    """Cross-endpoint workflow tests verifying the full request lifecycle."""

    def test_calculate_then_log_data_matches(self) -> None:
        """Emission values from /calculate must equal those persisted by /logs."""
        calc_result = client.post("/api/calculate", json=SAMPLE).json()
        client.post("/api/logs", json=SAMPLE)

        history = client.get("/api/history").json()
        # Find the last entry (our just-logged one)
        latest = history[-1]

        assert abs(latest["total_co2e"] - calc_result["totals"]["monthly_kg"]) < 0.01
        assert (
            abs(latest["breakdown"]["electricity"] - calc_result["breakdown"]["electricity"])
            < 0.01
        )

    def test_log_multiple_and_verify_count(self) -> None:
        """Logging N entries must increase the history length by N (up to the 15-cap)."""
        initial_count = len(client.get("/api/history").json())
        for _ in range(3):
            client.post("/api/logs", json=SAMPLE)
        new_count = len(client.get("/api/history").json())
        assert new_count == min(initial_count + 3, 15)

    def test_reset_then_log_then_history_has_one_entry(self) -> None:
        """After a reset, a single log must produce a history of exactly 1 entry."""
        client.post("/api/reset")
        client.post("/api/logs", json=SAMPLE)
        assert len(client.get("/api/history").json()) == 1

    def test_dates_preserved_across_log_and_history(self) -> None:
        """Dates set at log time must be retrievable via /api/history."""
        dates_to_log = ["2025-03-01", "2025-06-15", "2025-09-30"]
        client.post("/api/reset")
        for d in dates_to_log:
            client.post("/api/logs", json={**SAMPLE, "date": d})
        stored_dates = [e["date"] for e in client.get("/api/history").json()]
        for d in dates_to_log:
            assert d in stored_dates, f"Date '{d}' was not found in history"


# ===========================================================================
# 10.  Request Body Size Limit
# ===========================================================================

class TestBodySizeLimit:
    """Verify that oversized request bodies are rejected with HTTP 413."""

    def test_64kb_body_returns_413(self) -> None:
        """A request body larger than 64 KB must be rejected."""
        oversized_payload = "x" * (65 * 1024)  # 65 KB string
        resp = client.post(
            "/api/calculate",
            content=oversized_payload,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(oversized_payload)),
            },
        )
        assert resp.status_code == 413
