import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def base_dir():
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def fixtures_dir(base_dir):
    return base_dir / "tests" / "fixtures"


@pytest.fixture
def schema_path(base_dir):
    return base_dir / "Database" / "schema.sql"


@pytest.fixture
def temp_db(tmp_path, schema_path):
    """
    Creates an in-memory SQLite database initialized with schema.sql.
    """
    db_file = tmp_path / "test_snookerdb.db"

    with sqlite3.connect(db_file) as conn:
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        conn.commit()

    return db_file


@pytest.fixture
def load_fixture(fixtures_dir):
    def _load(filename):
        with open(fixtures_dir / filename, "r", encoding="utf-8") as f:
            return f.read()

    return _load
