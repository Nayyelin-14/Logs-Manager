
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["SYSLOG_ENABLED"] = "false"
os.environ["DATABASE_POOL"] = "null"
import pytest  # noqa: E402
@pytest.fixture(scope="session", autouse=True)
def test_database():

    yield
