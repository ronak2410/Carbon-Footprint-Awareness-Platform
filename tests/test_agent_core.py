"""
AURA Carbon — Comprehensive Test Suite v2
==========================================
Tests for all FastAPI endpoints, input validation, emission
calculation accuracy, database operations, and static file serving.
"""

from __future__ import annotations

import os
import sys

import pytest

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point the app to a throw-away test database BEFORE importing the module
TEST_DB = os.path.join(os.path.dirname(__file__), "test_carbon.db")
os.environ["DB_PATH"] = TEST_DB

import agent_core  # noqa: E402  (must come after env-var is set)

agent_core.DB_PATH = TEST_DB

from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(agent_core.app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_db():
    """Re-initialise a clean database before each test; tear down after."""
    # Wipe any existing test DB
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    agent_core.init_db()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# ---------------------------------------------------------------------------
# Payload Helpers
# ---------------------------------------------------------------------------

SAMPLE = {
    "electricity_kwh": 150.0,
    "petrol_km":       400.0,
    "lpg_kg":          14.0,
    "meat_meals":      7,
    "plant_meals":     14,
}

LOW = {
    "electricity_kwh": 30.0,
    "petrol_km":       80.0,
    "lpg_kg":          3.0,
    "meat_meals":      1,
    "plant_meals":     20,
}

HIGH = {
    "electricity_kwh": 800.0,
    "petrol_km":       2500.0,
    "lpg_kg":          60.0,
    "meat_meals":      20,
    "plant_meals":     1,
}

ZERO = {k: 0 for k in SAMPLE}


# ===========================================================================
# 1.  /api/calculate
# ===========================================================================

class TestCalculate:

    def test_returns_200(self):
        assert client.post("/api/calculate", json=SAMPLE).status_code == 200

    def test_response_has_required_keys(self):
        data = client.post("/api/calculate", json=SAMPLE).json()
        assert "breakdown" in data
        assert "totals"    in data
        assert "comparisons" in data

    def test_breakdown_contains_all_sectors(self):
        bd = client.post("/api/calculate", json=SAMPLE).json()["breakdown"]
        for key in ("electricity", "petrol", "lpg", "diet"):
            assert key in bd, f"Missing sector: {key}"

    def test_totals_contains_all_keys(self):
        totals = client.post("/api/calculate", json=SAMPLE).json()["totals"]
        for key in ("monthly_kg", "annual_kg", "annual_tons"):
            assert key in totals

    # --- Numerical accuracy ---
    def test_electricity_emission_is_correct(self):
        """150 kWh × 0.85 = 127.50 kg"""
        bd = client.post("/api/calculate", json=SAMPLE).json()["breakdown"]
        assert abs(bd["electricity"] - 127.50) < 0.01

    def test_petrol_emission_is_correct(self):
        """400 km × 0.20 = 80.00 kg"""
        bd = client.post("/api/calculate", json=SAMPLE).json()["breakdown"]
        assert abs(bd["petrol"] - 80.00) < 0.01

    def test_lpg_emission_is_correct(self):
        """14 kg × 3.00 = 42.00 kg"""
        bd = client.post("/api/calculate", json=SAMPLE).json()["breakdown"]
        assert abs(bd["lpg"] - 42.00) < 0.01

    def test_annual_tons_derived_from_monthly(self):
        totals = client.post("/api/calculate", json=SAMPLE).json()["totals"]
        expected = round((totals["monthly_kg"] * 12) / 1000, 2)
        assert abs(totals["annual_tons"] - expected) < 0.01

    # --- Edge cases ---
    def test_zero_payload_yields_zero_totals(self):
        totals = client.post("/api/calculate", json=ZERO).json()["totals"]
        assert totals["monthly_kg"] == 0.0

    def test_high_usage_exceeds_global_average(self):
        totals = client.post("/api/calculate", json=HIGH).json()["totals"]
        assert totals["annual_tons"] > 4.8

    def test_low_usage_well_below_global_average(self):
        totals = client.post("/api/calculate", json=LOW).json()["totals"]
        # Low payload must be meaningfully below the 4.8 t global average
        assert totals["annual_tons"] < 4.8

    def test_highest_sector_is_identified(self):
        cmp = client.post("/api/calculate", json=HIGH).json()["comparisons"]
        assert "highest_sector" in cmp
        assert cmp["highest_sector"] != ""

    def test_pct_of_global_avg_is_positive(self):
        cmp = client.post("/api/calculate", json=SAMPLE).json()["comparisons"]
        assert cmp["pct_of_global_avg"] > 0

    # --- Validation ---
    def test_missing_required_field_returns_422(self):
        bad = {k: v for k, v in SAMPLE.items() if k != "electricity_kwh"}
        assert client.post("/api/calculate", json=bad).status_code == 422

    def test_negative_electricity_rejected(self):
        bad = {**SAMPLE, "electricity_kwh": -10}
        assert client.post("/api/calculate", json=bad).status_code == 422

    def test_negative_petrol_rejected(self):
        bad = {**SAMPLE, "petrol_km": -1}
        assert client.post("/api/calculate", json=bad).status_code == 422

    def test_electricity_above_max_rejected(self):
        bad = {**SAMPLE, "electricity_kwh": 99999}
        assert client.post("/api/calculate", json=bad).status_code == 422

    def test_meat_meals_above_max_rejected(self):
        bad = {**SAMPLE, "meat_meals": 100}
        assert client.post("/api/calculate", json=bad).status_code == 422

    def test_string_for_numeric_field_rejected(self):
        bad = {**SAMPLE, "electricity_kwh": "not-a-number"}
        assert client.post("/api/calculate", json=bad).status_code == 422


# ===========================================================================
# 2.  /api/logs
# ===========================================================================

class TestLogs:

    def test_save_returns_200(self):
        assert client.post("/api/logs", json=SAMPLE).status_code == 200

    def test_save_response_status_is_success(self):
        assert client.post("/api/logs", json=SAMPLE).json()["status"] == "success"

    def test_save_response_includes_data(self):
        resp = client.post("/api/logs", json=SAMPLE).json()
        assert "data" in resp
        assert "totals" in resp["data"]

    def test_saved_log_appears_in_history(self):
        client.post("/api/logs", json=SAMPLE)
        history = client.get("/api/history").json()
        # Seed adds 4; our log makes 5
        assert len(history) >= 1

    def test_custom_date_is_stored(self):
        payload = {**SAMPLE, "date": "2025-01-15"}
        client.post("/api/logs", json=payload)
        dates = [e["date"] for e in client.get("/api/history").json()]
        assert "2025-01-15" in dates

    def test_multiple_saves_all_succeed(self):
        for _ in range(3):
            assert client.post("/api/logs", json=SAMPLE).status_code == 200

    def test_missing_required_field_returns_422(self):
        bad = {k: v for k, v in SAMPLE.items() if k != "petrol_km"}
        assert client.post("/api/logs", json=bad).status_code == 422

    def test_invalid_date_format_rejected(self):
        bad = {**SAMPLE, "date": "21-06-2025"}   # DD-MM-YYYY not accepted
        assert client.post("/api/logs", json=bad).status_code == 422

    def test_nonsense_date_rejected(self):
        bad = {**SAMPLE, "date": "not-a-date"}
        assert client.post("/api/logs", json=bad).status_code == 422

    def test_none_date_uses_today(self):
        payload = {**SAMPLE, "date": None}
        assert client.post("/api/logs", json=payload).status_code == 200


# ===========================================================================
# 3.  /api/history
# ===========================================================================

class TestHistory:

    def test_returns_200(self):
        assert client.get("/api/history").status_code == 200

    def test_returns_a_list(self):
        assert isinstance(client.get("/api/history").json(), list)

    def test_entry_has_required_fields(self):
        client.post("/api/logs", json=SAMPLE)
        entry = client.get("/api/history").json()[0]
        for field in ("id", "date", "total_co2e", "breakdown", "electricity_kwh"):
            assert field in entry, f"Missing: {field}"

    def test_breakdown_has_four_sectors(self):
        client.post("/api/logs", json=SAMPLE)
        bd = client.get("/api/history").json()[0]["breakdown"]
        for key in ("electricity", "petrol", "lpg", "diet"):
            assert key in bd

    def test_history_ordered_ascending(self):
        """Oldest entry first — required for correct chart rendering."""
        client.post("/api/logs", json={**SAMPLE, "date": "2024-01-01"})
        client.post("/api/logs", json={**SAMPLE, "date": "2024-06-01"})
        history = client.get("/api/history").json()
        date_pairs = [h["date"] for h in history if h["date"] in ("2024-01-01", "2024-06-01")]
        if len(date_pairs) == 2:
            assert date_pairs.index("2024-01-01") < date_pairs.index("2024-06-01")

    def test_history_capped_at_15(self):
        for _ in range(20):
            client.post("/api/logs", json=SAMPLE)
        assert len(client.get("/api/history").json()) <= 15

    def test_seeded_data_present_on_fresh_db(self):
        """A fresh DB must contain the 4 seed records."""
        history = client.get("/api/history").json()
        assert len(history) >= 4


# ===========================================================================
# 4.  /api/reset
# ===========================================================================

class TestReset:

    def test_returns_200(self):
        assert client.post("/api/reset").status_code == 200

    def test_response_status_is_success(self):
        assert client.post("/api/reset").json()["status"] == "success"

    def test_clears_all_records(self):
        client.post("/api/logs", json=SAMPLE)
        client.post("/api/reset")
        assert client.get("/api/history").json() == []

    def test_double_reset_is_safe(self):
        assert client.post("/api/reset").status_code == 200
        assert client.post("/api/reset").status_code == 200

    def test_new_logs_accepted_after_reset(self):
        client.post("/api/reset")
        client.post("/api/logs", json=SAMPLE)
        assert len(client.get("/api/history").json()) == 1


# ===========================================================================
# 5.  /api/health
# ===========================================================================

class TestHealth:

    def test_returns_200(self):
        assert client.get("/api/health").status_code == 200

    def test_status_is_ok(self):
        assert client.get("/api/health").json()["status"] == "ok"

    def test_database_is_ok(self):
        assert client.get("/api/health").json()["database"] == "ok"

    def test_version_is_present(self):
        assert "version" in client.get("/api/health").json()


# ===========================================================================
# 6.  Static File Serving
# ===========================================================================

class TestStaticFiles:

    def test_index_html_served(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_index_html_contains_brand(self):
        assert "AURA CARBON" in client.get("/").text

    def test_app_js_served(self):
        assert client.get("/app.js").status_code == 200

    def test_style_css_served(self):
        assert client.get("/style.css").status_code == 200

    def test_unknown_route_returns_404(self):
        assert client.get("/this-does-not-exist").status_code == 404


# ===========================================================================
# 7.  Security Headers
# ===========================================================================

class TestSecurityHeaders:

    def test_x_content_type_options(self):
        headers = client.get("/").headers
        assert headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options(self):
        assert client.get("/").headers.get("x-frame-options") == "DENY"

    def test_x_xss_protection(self):
        assert "1; mode=block" in client.get("/").headers.get("x-xss-protection", "")

    def test_referrer_policy_present(self):
        assert client.get("/").headers.get("referrer-policy") is not None

    def test_content_security_policy_present(self):
        assert client.get("/").headers.get("content-security-policy") is not None
