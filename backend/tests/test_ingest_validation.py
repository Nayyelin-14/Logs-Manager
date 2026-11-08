from fastapi.testclient import TestClient
from app.main import app


class TestIngestValidation:

    def test_empty_body_returns_400(self, api_key):
        client = TestClient(app)
        res = client.post(
            "/ingest",
            content=b"",
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
        )
        assert res.status_code == 400, f"expected 400, got {res.status_code}: {res.text}"

    def test_invalid_json_returns_400(self, api_key):
        client = TestClient(app)
        res = client.post(
            "/ingest",
            content=b"not json",
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
        )
        assert res.status_code == 400, f"expected 400, got {res.status_code}: {res.text}"

    def test_non_utf8_returns_400(self, api_key):
        client = TestClient(app)
        res = client.post(
            "/ingest",
            content=b"\x80\x81\x82",
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
        )
        assert res.status_code == 400, f"expected 400, got {res.status_code}: {res.text}"

    def test_empty_object_returns_422(self, api_key):
        client = TestClient(app)
        res = client.post(
            "/ingest",
            json={},
            headers={"X-API-Key": api_key},
        )
        assert res.status_code == 422, f"expected 422, got {res.status_code}: {res.text}"

    def test_invalid_timestamp_returns_422(self, api_key):
        client = TestClient(app)
        res = client.post(
            "/ingest",
            json={"tenant": "demoA", "source": "api", "event_type": "test", "@timestamp": "not-a-date"},
            headers={"X-API-Key": api_key},
        )
        assert res.status_code == 422, f"expected 422, got {res.status_code}: {res.text}"

    def test_unknown_source_returns_400(self, api_key):
        client = TestClient(app)
        res = client.post(
            "/ingest",
            json={"tenant": "demoA", "source": "unknown_source", "event_type": "test"},
            headers={"X-API-Key": api_key},
        )
        assert res.status_code == 400, f"expected 400, got {res.status_code}: {res.text}"

    def test_valid_event_returns_200(self, api_key):
        client = TestClient(app)
        res = client.post(
            "/ingest",
            json={"tenant": "demoA", "source": "api", "event_type": "test", "user": "alice"},
            headers={"X-API-Key": api_key},
        )
        assert res.status_code == 200, f"expected 200, got {res.status_code}: {res.text}"

    def test_batch_invalid_timestamp_returns_422(self, api_key):
        client = TestClient(app)
        res = client.post(
            "/ingest/batch",
            json={"events": [{"source": "api", "event_type": "good"}, {"source": "api", "event_type": "bad", "@timestamp": "bad-date"}]},
            headers={"X-API-Key": api_key},
        )
        assert res.status_code == 422, f"expected 422, got {res.status_code}: {res.text}"

    def test_batch_one_bad_does_not_discard_good(self, api_key):
        client = TestClient(app)
        res = client.post(
            "/ingest/batch",
            json={
                "events": [
                    {"source": "api", "event_type": "good1", "user": "a"},
                    {"source": "api", "event_type": "good2", "user": "b"},
                ]
            },
            headers={"X-API-Key": api_key},
        )
        assert res.status_code == 200, f"expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["ingested"] == 2, f"expected 2 ingested, got {data['ingested']}"
