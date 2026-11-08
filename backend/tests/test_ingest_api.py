import json

from app.core.config import get_settings

MARKER = "phase2-ingest-api"


from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    VIEWER_A_EMAIL,
    VIEWER_A_PASSWORD,
    VIEWER_B_EMAIL,
    VIEWER_B_PASSWORD,
)
def _headers(api_key: str, tenant: str | None = None) -> dict:
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    return headers


def test_single_event_ingest_lands_in_api_key_tenant(client, api_key):
    src_ip = "198.51.100.21"
    event = {
        "source": "firewall",
        "event_type": "traffic_blocked",
        "action": "DENY",
        "src_ip": src_ip,
        "dst_ip": "203.0.113.9",
        "protocol": "udp",
        "severity": 5,
        "vendor": "unit-test",
        "product": "ngfw",
        "description": MARKER,
    }
    res = client.post("/api/ingest", json=event, headers=_headers(api_key))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["eventId"]
    assert body["ingested"] == 1

    login = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200
    logs = client.get("/api/get-logs", params={"src_ip": src_ip}).json()["logs"]
    assert len(logs) >= 1
    assert logs[0]["tenant"] == "demoa"
    assert logs[0]["source"] == "firewall"


def test_batch_ingest_counts_per_record(client, api_key):
    events = [
        {"source": "api", "event_type": f"{MARKER}_batch_{i}", "severity": 3, "action": "LOGIN"}
        for i in range(3)
    ]
    res = client.post(
        "/api/ingest/batch", json={"events": events}, headers=_headers(api_key)
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ingested"] == 3
    assert body["rejected"] == 0
    assert body["parsed"] == 3


def test_unsupported_source_is_rejected(client, api_key):
    res = client.post(
        "/api/ingest",
        json={"source": "skynet", "event_type": "test"},
        headers=_headers(api_key),
    )
    assert res.status_code == 400, res.text
    assert "Unsupported source" in res.json()["detail"]


def test_cross_tenant_ingest_is_denied(client, api_key):
    res = client.post(
        "/api/ingest",
        json={"source": "api", "event_type": "cross_tenant_probe", "tenant": "demob"},
        headers=_headers(api_key),
    )
    assert res.status_code == 403, res.text
    assert "demob" in res.json()["detail"]


def test_ingest_accepts_capitalised_tenant_in_body_with_correct_key(client, api_key_demob):
    res = client.post(
        "/api/ingest",
        json={"source": "api", "event_type": "case_test", "tenant": "demoB"},
        headers=_headers(api_key_demob),
    )

    print(f"Response status: {res.status_code}, body: {res.text}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["ingested"] == 1
    event_id = body["eventId"]


    login = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200
    logs = client.get("/api/get-logs", params={"limit": 100}).json()["logs"]
    found = [l for l in logs if l.get("id") == event_id]
    assert len(found) == 1
    assert found[0]["tenant"] == "demob"


    viewer_b = client.post("/api/auth/login", json={"email": VIEWER_B_EMAIL, "password": VIEWER_B_PASSWORD})
    assert viewer_b.status_code == 200

    from fastapi.testclient import TestClient
    from app.main import app
    viewer_b_client = TestClient(app)
    viewer_b_client.post("/api/auth/login", json={"email": VIEWER_B_EMAIL, "password": VIEWER_B_PASSWORD})
    res = viewer_b_client.get("/api/get-logs", params={"limit": 100})
    logs = res.json()["logs"]
    found = [l for l in logs if l.get("id") == event_id]
    assert len(found) == 1, "viewerB should see the event"


    viewer_a_client = TestClient(app)
    viewer_a_client.post("/api/auth/login", json={"email": VIEWER_A_EMAIL, "password": VIEWER_A_PASSWORD})
    res = viewer_a_client.get("/api/get-logs", params={"limit": 100})
    logs = res.json()["logs"]
    found = [l for l in logs if l.get("id") == event_id]
    assert len(found) == 0, "viewerA should NOT see the event"


def test_file_upload_jsonl_with_bad_line(client, api_key):
    content = (
        json.dumps({"source": "api", "event_type": f"{MARKER}_file_0"}) + "\n"
        + "{not valid json\n"
        + json.dumps({"source": "api", "event_type": f"{MARKER}_file_1"}) + "\n"
    ).encode()
    res = client.post(
        "/api/ingest/file",
        files={"file": ("probe.jsonl", content, "application/x-ndjson")},
        headers={"X-API-Key": api_key},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["format"] == "jsonl"
    assert body["parsed"] == 3
    assert body["ingested"] == 2
    assert body["rejected"] == 1
    assert any("Invalid JSON" in e.get("error", "") for e in body["errors"])


def test_file_upload_csv(client, api_key):
    content = (
        "source,event_type,severity,src_ip,action\n"
        f"api,{MARKER}_csv,4,198.51.100.31,LOGIN\n"
        f"api,{MARKER}_csv2,6,198.51.100.32,LOGIN\n"
    ).encode()
    res = client.post(
        "/api/ingest/file",
        files={"file": ("probe.csv", content, "text/csv")},
        headers={"X-API-Key": api_key},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["format"] == "csv"
    assert body["ingested"] == 2
    assert body["rejected"] == 0


def test_file_upload_rejects_disallowed_extension(client, api_key):
    res = client.post(
        "/api/ingest/file",
        files={"file": ("payload.exe", b"MZ....", "application/octet-stream")},
        headers={"X-API-Key": api_key},
    )
    assert res.status_code == 400, res.text
    assert "Unsupported file type" in res.json()["detail"]


def test_file_upload_rejects_empty_file(client, api_key):
    res = client.post(
        "/api/ingest/file",
        files={"file": ("empty.json", b"", "application/json")},
        headers={"X-API-Key": api_key},
    )
    assert res.status_code == 400, res.text


def test_file_upload_rejects_oversized_file(client, api_key, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "INGEST_MAX_FILE_BYTES", 64)
    res = client.post(
        "/api/ingest/file",
        files={"file": ("big.json", b"[" + b" " * 128 + b"]", "application/json")},
        headers={"X-API-Key": api_key},
    )
    assert res.status_code == 413, res.text


def test_ingest_requires_api_key(client):
    res = client.post("/api/ingest", json={"source": "api", "event_type": "no_key"})
    assert res.status_code in (401, 403), res.text


def test_viewer_search_is_tenant_scoped(viewer_a_client):
    res = viewer_a_client.get("/api/get-logs", params={"limit": 100})
    assert res.status_code == 200, res.text
    tenants = {log["tenant"] for log in res.json()["logs"]}
    assert tenants <= {"demoa"}, f"viewerA saw tenants: {tenants}"

    res_forced = viewer_a_client.get(
        "/api/get-logs", params={"tenant": "demob", "limit": 100}
    )
    assert res_forced.status_code == 200
    assert all(log["tenant"] != "demob" for log in res_forced.json()["logs"])


def test_viewer_cannot_call_admin_endpoints(viewer_a_client):
    res = viewer_a_client.get("/api/get-all-data")
    assert res.status_code == 403, res.text

    res = viewer_a_client.post(
        "/api/create-alertRule",
        json={"name": "x", "tenant": "demoA", "conditions": [{"type": "severity_min"}]},
    )
    assert res.status_code == 403, res.text
