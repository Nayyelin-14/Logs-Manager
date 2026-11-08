import pytest

from app.parsers.identity import normalize_ad
from app.models.enums import Source


class TestADWindowsBasic:

    def test_normalize_4624_logon_success(self):
        raw = {
            "EventID": 4624,
            "TargetUserName": "alice",
            "SubjectUserName": "alice",
            "Computer": "DC01.corp.example.com",
            "IpAddress": "10.0.0.77",
            "LogonType": 3,
            "Status": "0x0",
            "Message": "An account was successfully logged on",
            "TimeCreated": "2026-10-30T22:19:00Z",
        }

        result = normalize_ad(raw)

        assert result["source"] == Source.AD
        assert result["event_type"] == "ad_logon_success"
        assert result["canonical_event_type"] == "ad_logon_success"
        assert result["user"] == "alice"
        assert result["src_ip"] == "10.0.0.77"
        assert result["host"] == "DC01.corp.example.com"
        assert result["event_id"] == 4624
        assert result["logon_type"] == 3

    def test_normalize_4625_logon_failure(self):
        raw = {
            "EventID": 4625,
            "TargetUserName": "alice",
            "Computer": "DC01.corp.example.com",
            "IpAddress": "10.0.0.77",
            "LogonType": 3,
            "Status": "0xC000006D",
            "Message": "An account failed to log on",
            "TimeCreated": "2026-10-30T22:19:00Z",
        }

        result = normalize_ad(raw)

        assert result["source"] == Source.AD
        assert result["event_type"] == "ad_logon_failed"
        assert result["canonical_event_type"] == "ad_logon_failed"
        assert result["event_id"] == 4625
        assert result["user"] == "alice"
        assert result["outcome"] == "failure"

    def test_timestamp_utc_conversion(self):
        raw = {"TimeCreated": "2026-10-30T22:19:00Z"}

        result = normalize_ad(raw)

        assert result["timestamp"] == "2026-10-30T22:19:00+00:00"

    def test_raw_preserved(self):
        raw = {"EventID": 4624, "extra": "data"}

        result = normalize_ad(raw)

        assert "EventID" in result["raw"]


class TestADEventIdMapping:

    def test_4624_succeeds(self):
        raw = {"EventID": 4624}

        result = normalize_ad(raw)

        assert result["event_type"] == "ad_logon_success"

    def test_4625_fails(self):
        raw = {"EventID": 4625}

        result = normalize_ad(raw)

        assert result["event_type"] == "ad_logon_failed"

    def test_4634_logoff(self):
        raw = {"EventID": 4634}

        result = normalize_ad(raw)

        assert result["event_type"] == "ad_logoff"

    def test_4720_user_created(self):
        raw = {"EventID": 4720}

        result = normalize_ad(raw)

        assert result["event_type"] == "ad_user_created"

    def test_4726_user_deleted(self):
        raw = {"EventID": 4726}

        result = normalize_ad(raw)

        assert result["event_type"] == "ad_user_deleted"


class TestADActionMapping:

    def test_4624_login_action(self):
        raw = {"EventID": 4624}

        result = normalize_ad(raw)

        assert result["action"] == "LOGIN"

    def test_4625_login_action(self):
        raw = {"EventID": 4625}

        result = normalize_ad(raw)

        assert result["action"] == "LOGIN"

    def test_4634_logout_action(self):
        raw = {"EventID": 4634}

        result = normalize_ad(raw)

        assert result["action"] == "LOGOUT"

    def test_4720_create_user_action(self):
        raw = {"EventID": 4720}

        result = normalize_ad(raw)

        assert result["action"] == "CREATE"

    def test_4726_delete_action(self):
        raw = {"EventID": 4726}

        result = normalize_ad(raw)

        assert result["action"] == "DELETE"


class TestADOutcome:

    def test_4624_success(self):
        raw = {"EventID": 4624}

        result = normalize_ad(raw)

        assert result["outcome"] == "success"

    def test_4625_failure(self):
        raw = {"EventID": 4625}

        result = normalize_ad(raw)

        assert result["outcome"] == "failure"

    def test_4634_unknown(self):
        raw = {"EventID": 4634}

        result = normalize_ad(raw)

        assert result["outcome"] == "unknown"
