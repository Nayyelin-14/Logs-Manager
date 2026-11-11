
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["SYSLOG_ENABLED"] = "false"
os.environ["DATABASE_POOL"] = "null"
import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_database():

    yield


@pytest.fixture(scope="session", autouse=True)
def db_baseline(test_database):
    """Unit tests do not touch the database, so skip the parent snapshot."""
    return {}


@pytest.fixture(scope="module", autouse=True)
def isolate_db(db_baseline):
    """Unit tests do not touch the database, so skip the parent cleanup."""
    yield
