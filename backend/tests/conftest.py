import importlib
import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def test_client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["METRICS_ENABLED"] = "true"

    import app.config as config
    import app.database as database
    import app.models as models
    import app.store as store
    import app.main as main
    import app.rate_limit as rate_limit

    importlib.reload(config)
    importlib.reload(database)
    importlib.reload(models)
    importlib.reload(store)
    importlib.reload(main)
    rate_limit.RATE_LIMIT_POLICIES = []

    with TestClient(main.app) as client:
        yield client


@pytest.fixture()
def registered_user(test_client):
    payload = {"email": f"user-{uuid.uuid4().hex[:8]}@example.com", "password": "strongpass123"}
    r = test_client.post("/api/v1/auth/register", json=payload)
    if r.status_code != 200:
        raise AssertionError(r.text)
    return r.json()["user"], payload


@pytest.fixture()
def auth_headers(test_client, registered_user):
    _, creds = registered_user
    r = test_client.post("/api/v1/auth/login", json=creds)
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
