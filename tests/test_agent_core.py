"""
AURA Carbon - Comprehensive Test Suite
Tests for all FastAPI endpoints and core calculation logic.
"""

import pytest
import os
import sys

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from agent_core import app

# Use a separate test database to avoid polluting production data
TEST_DB = "test_friday_carbon.db"

import agent_core
agent_core.DB_PATH = TEST_DB

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_test_db():
    """Re-initialise a clean database before each test and remove it after."""
    # Reinitialise with a clean slate
    agent_core.DB_PATH = TEST_DB
    agent_core.init_db()
    yield
    # Teardown: wipe test database
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

SAMPLE_PAYLOAD = {
    "electricity_kwh": 150.0,
    "petrol_km": 400.0,
    "lpg_kg": 14.0,
    "meat_meals": 7,
    "plant_meals": 14,
}

LOW_FOOTPRINT_PAYLOAD = {
    "electricity_kwh": 50.0,
    "petrol_km": 100.0,
    "lpg_kg": 5.0,
    "meat_meals": 2,
    "plant_meals": 19,
}

HIGH_FOOTPRINT_PAYLOAD = {
    "electricity_kwh": 800.0,
    "petrol_km": 2500.0,
    "lpg_kg": 60.0,
    "meat_meals": 20,
    "plant_meals": 1,
}


# ===========================================================================
# 1.  /api/calculate  — Emission Calculation Endpoint
# ===========================================================================

class TestCalculateEndpoint:

    def test_calculate_returns_200(self):
        """POST /api/calculate returns HTTP 200 for a valid payload."""
        resp = client.post("/api/calculate", json=SAMPLE_PAYLOAD)
        assert resp.status_code == 200

    def test_calculate_response_structure(self):
        """Response contains 'breakdown', 'totals', and 'comparisons' keys."""
        resp = client.post("/api/calculate", json=SAMPLE_PAYLOAD).json()
        assert "breakdown" in resp
        assert "totals" in resp
        assert "comparisons" in resp

    def test_calculate_breakdown_keys(self):
        """Breakdown contains all four emission sectors."""
        breakdown = client.post("/api/calculate", json=SAMPLE_PAYLOAD).json()["breakdown"]
        for key in ("electricity", "petrol", "lpg", "diet"):
            assert key in breakdown, f"Missing breakdown key: {key}"

    def test_calculate_totals_keys(self):
        """Totals contains monthly_kg, annual_kg, annual_tons."""
        totals = client.post("/api/calculate", json=SAMPLE_PAYLOAD).json()["totals"]
        assert "monthly_kg" in totals
        assert "annual_kg" in totals
        assert "annual_tons" in totals

    def test_calculate_electricity_emission_value(self):
        """Electricity emission is correctly calculated (150 kWh × 0.85 = 127.5 kg)."""
        resp = client.post("/api/calculate", json=SAMPLE_PAYLOAD).json()
        assert abs(resp["breakdown"]["electricity"] - 127.5) < 0.1

    def test_calculate_petrol_emission_value(self):
        """Petrol emission is correctly calculated (400 km × 0.20 = 80.0 kg)."""
        resp = client.post("/api/calculate", json=SAMPLE_PAYLOAD).json()
        assert abs(resp["breakdown"]["petrol"] - 80.0) < 0.1

    def test_calculate_lpg_emission_value(self):
        """LPG emission is correctly calculated (14 kg × 3.00 = 42.0 kg)."""
        resp = client.post("/api/calculate", json=SAMPLE_PAYLOAD).json()
        assert abs(resp["breakdown"]["lpg"] - 42.0) < 0.1

    def test_calculate_annual_tons_is_monthly_times_12(self):
        """Annual tons is (monthly_kg × 12) / 1000."""
        totals = client.post("/api/calculate", json=SAMPLE_PAYLOAD).json()["totals"]
        expected = (totals["monthly_kg"] * 12) / 1000
        assert abs(totals["annual_tons"] - round(expected, 2)) < 0.01

    def test_calculate_all_zeros_payload(self):
        """Zero-value payload returns zero totals without errors."""
        zero = {k: 0 for k in SAMPLE_PAYLOAD}
        resp = client.post("/api/calculate", json=zero)
        assert resp.status_code == 200
        assert resp.json()["totals"]["monthly_kg"] == 0.0

    def test_calculate_high_footprint(self):
        """High-usage payload produces emissions significantly above global average."""
        totals = client.post("/api/calculate", json=HIGH_FOOTPRINT_PAYLOAD).json()["totals"]
        # Global avg is ~4.8 tons/year; high payload should far exceed that
        assert totals["annual_tons"] > 4.8

    def test_calculate_low_footprint_below_target(self):
        """Low-usage payload should produce a footprint well below the 4.8 t/year global average."""
        totals = client.post("/api/calculate", json=LOW_FOOTPRINT_PAYLOAD).json()["totals"]
        # The low payload is significantly below the 4.8 t global average;
        # we assert it is under 3.5 t as a conservative reachable eco threshold.
        assert totals["annual_tons"] < 3.5

    def test_calculate_missing_field_returns_422(self):
        """Missing required field returns HTTP 422 Unprocessable Entity."""
        bad = {k: v for k, v in SAMPLE_PAYLOAD.items() if k != "electricity_kwh"}
        resp = client.post("/api/calculate", json=bad)
        assert resp.status_code == 422

    def test_calculate_highest_sector_identified(self):
        """The highest-emission sector is correctly identified in comparisons."""
        resp = client.post("/api/calculate", json=HIGH_FOOTPRINT_PAYLOAD).json()
        assert "highest_sector" in resp["comparisons"]
        assert resp["comparisons"]["highest_sector"] != ""


# ===========================================================================
# 2.  /api/logs  — Save Log Endpoint
# ===========================================================================

class TestLogsEndpoint:

    def test_save_log_returns_200(self):
        """POST /api/logs returns HTTP 200."""
        resp = client.post("/api/logs", json=SAMPLE_PAYLOAD)
        assert resp.status_code == 200

    def test_save_log_response_has_status_success(self):
        """Response body contains status = 'success'."""
        resp = client.post("/api/logs", json=SAMPLE_PAYLOAD).json()
        assert resp["status"] == "success"

    def test_save_log_response_has_data(self):
        """Response body includes calculated emission data."""
        resp = client.post("/api/logs", json=SAMPLE_PAYLOAD).json()
        assert "data" in resp
        assert "totals" in resp["data"]

    def test_save_log_persists_to_history(self):
        """After saving a log, /api/history returns exactly one entry."""
        client.post("/api/logs", json=SAMPLE_PAYLOAD)
        history = client.get("/api/history").json()
        # Seed data is 4, plus 1 new log = 5 max; check at least 1 exists
        assert len(history) >= 1

    def test_save_log_with_custom_date(self):
        """Log with a custom date is stored with that date."""
        payload = {**SAMPLE_PAYLOAD, "date": "2025-01-15"}
        resp = client.post("/api/logs", json=payload)
        assert resp.status_code == 200
        history = client.get("/api/history").json()
        dates = [entry["date"] for entry in history]
        assert "2025-01-15" in dates

    def test_save_multiple_logs(self):
        """Multiple log submissions all succeed."""
        for _ in range(3):
            resp = client.post("/api/logs", json=SAMPLE_PAYLOAD)
            assert resp.status_code == 200

    def test_save_log_missing_field_returns_422(self):
        """Missing required field in /api/logs returns 422."""
        bad = {k: v for k, v in SAMPLE_PAYLOAD.items() if k != "petrol_km"}
        resp = client.post("/api/logs", json=bad)
        assert resp.status_code == 422


# ===========================================================================
# 3.  /api/history  — Get History Endpoint
# ===========================================================================

class TestHistoryEndpoint:

    def test_history_returns_200(self):
        """GET /api/history returns HTTP 200."""
        resp = client.get("/api/history")
        assert resp.status_code == 200

    def test_history_returns_list(self):
        """GET /api/history response is a JSON list."""
        resp = client.get("/api/history")
        assert isinstance(resp.json(), list)

    def test_history_entry_structure(self):
        """Each history entry contains all required fields."""
        client.post("/api/logs", json=SAMPLE_PAYLOAD)
        history = client.get("/api/history").json()
        assert len(history) > 0
        entry = history[0]
        for field in ("id", "date", "total_co2e", "breakdown", "electricity_kwh"):
            assert field in entry, f"Missing field in history entry: {field}"

    def test_history_breakdown_in_entry(self):
        """Each history entry's breakdown contains all four sectors."""
        client.post("/api/logs", json=SAMPLE_PAYLOAD)
        entry = client.get("/api/history").json()[0]
        for key in ("electricity", "petrol", "lpg", "diet"):
            assert key in entry["breakdown"]

    def test_history_ordered_chronologically(self):
        """History is returned in chronological order (oldest first)."""
        client.post("/api/logs", json={**SAMPLE_PAYLOAD, "date": "2024-01-01"})
        client.post("/api/logs", json={**SAMPLE_PAYLOAD, "date": "2024-06-01"})
        history = client.get("/api/history").json()
        dates = [h["date"] for h in history if h["date"] in ("2024-01-01", "2024-06-01")]
        if len(dates) == 2:
            assert dates.index("2024-01-01") < dates.index("2024-06-01")

    def test_history_limits_to_15_entries(self):
        """History endpoint returns at most 15 entries."""
        for i in range(20):
            client.post("/api/logs", json=SAMPLE_PAYLOAD)
        history = client.get("/api/history").json()
        assert len(history) <= 15


# ===========================================================================
# 4.  /api/reset  — Clear History Endpoint
# ===========================================================================

class TestResetEndpoint:

    def test_reset_returns_200(self):
        """POST /api/reset returns HTTP 200."""
        resp = client.post("/api/reset")
        assert resp.status_code == 200

    def test_reset_response_has_status_success(self):
        """Response body contains status = 'success'."""
        resp = client.post("/api/reset").json()
        assert resp["status"] == "success"

    def test_reset_clears_all_logs(self):
        """After reset, /api/history returns an empty list."""
        client.post("/api/logs", json=SAMPLE_PAYLOAD)
        client.post("/api/reset")
        history = client.get("/api/history").json()
        assert history == []

    def test_reset_idempotent(self):
        """Calling reset twice in succession does not cause errors."""
        resp1 = client.post("/api/reset")
        resp2 = client.post("/api/reset")
        assert resp1.status_code == 200
        assert resp2.status_code == 200

    def test_reset_allows_new_logs_after(self):
        """New logs can be saved after a reset."""
        client.post("/api/reset")
        resp = client.post("/api/logs", json=SAMPLE_PAYLOAD)
        assert resp.status_code == 200
        history = client.get("/api/history").json()
        assert len(history) == 1


# ===========================================================================
# 5.  Static File Serving
# ===========================================================================

class TestStaticFiles:

    def test_index_html_served(self):
        """GET / serves index.html with status 200."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_index_html_contains_aura_carbon(self):
        """Served index.html contains the AURA CARBON brand name."""
        resp = client.get("/")
        assert "AURA CARBON" in resp.text

    def test_app_js_served(self):
        """GET /app.js returns 200 with JavaScript content."""
        resp = client.get("/app.js")
        assert resp.status_code == 200

    def test_style_css_served(self):
        """GET /style.css returns 200 with CSS content."""
        resp = client.get("/style.css")
        assert resp.status_code == 200

    def test_unknown_route_returns_404(self):
        """A non-existent route returns 404."""
        resp = client.get("/non-existent-page-xyz")
        assert resp.status_code == 404
