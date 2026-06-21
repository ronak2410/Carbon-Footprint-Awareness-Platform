"""
Shared pytest configuration and fixtures for the AURA Carbon test suite.

This conftest.py is automatically loaded by pytest before any test module
is collected. It provides:
- Isolation via a temporary test database path injected via environment variable
- The ``clean_db`` autouse fixture (database reset before/after every test)
- Shared test-client instance available to all test modules

Usage:
    Run the full suite:   pytest
    Run a single class:   pytest tests/test_agent_core.py::TestCalculate -v
"""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — ensure the project root is importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Inject test database path BEFORE the application module is imported
# so that agent_core.DB_PATH picks it up at module-load time.
# ---------------------------------------------------------------------------
_TEST_DB_PATH = str(Path(__file__).parent / "test_carbon.db")
os.environ.setdefault("DB_PATH", _TEST_DB_PATH)

from fastapi.testclient import TestClient  # noqa: E402

import agent_core  # noqa: E402  (intentionally after env-var is set)

# Patch the runtime attribute in case the module was already loaded
agent_core.DB_PATH = _TEST_DB_PATH

# Shared, module-level test client (created once; no performance overhead per test)
client: TestClient = TestClient(agent_core.app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_db() -> Generator[None, None, None]:
    """
    Autouse fixture — runs before and after every test.

    Guarantees a pristine database state for each test by:
    1. Removing any existing test database file.
    2. Re-running ``init_db()`` to create the schema and seed data.
    3. Yielding control to the test body.
    4. Removing the database file again on teardown.
    """
    db_path = Path(_TEST_DB_PATH)
    if db_path.exists():
        db_path.unlink()
    agent_core.init_db()
    yield
    if db_path.exists():
        db_path.unlink()


@pytest.fixture()
def api_client() -> TestClient:
    """Return the shared ``TestClient`` for use in individual tests."""
    return client
