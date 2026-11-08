import pytest

from app.parsers.identity import normalize_ad
from app.models.enums import Source


class TestADSeverity:

    def test_4625_severity_7(self):
        raw = {"EventID": 4625}

        result = normalize_ad(raw)

        assert result["severity"] == 7

    def test_4624_severity_3(self):
        raw = {"EventID": 4624}

        result = normalize_ad(raw)

        assert result["severity"] == 3

    def test_explicit_severity_used(self):
        raw = {"EventID": 4624, "severity": 8}

        result = normalize_ad(raw)

        assert result["severity"] == 8


class TestADIPExtraction:

    def test_ip_address_extraction(self):
        raw = {"IpAddress": "192.168.1.50"}

        result = normalize_ad(raw)

        assert result["src_ip"] == "192.168.1.50"

    def test_ip_from_event_field(self):
        raw = {"ip": "10.0.0.100"}

        result = normalize_ad(raw)

        assert result["src_ip"] == "10.0.0.100"

    def test_invalid_ip_not_validated(self):
        raw = {"IpAddress": "not-an-ip"}

        result = normalize_ad(raw)

        assert result["src_ip"] == "not-an-ip"


class TestADUserExtraction:

    def test_target_user_name(self):
        raw = {"TargetUserName": "testuser"}

        result = normalize_ad(raw)

        assert result["user"] == "testuser"

    def test_subject_user_name(self):
        raw = {"SubjectUserName": "subjectuser"}

        result = normalize_ad(raw)

        assert result["user"] == "subjectuser"

    def test_user_name_field(self):
        raw = {"user_name": "fielduser"}

        result = normalize_ad(raw)

        assert result["user"] == "fielduser"


class TestADHostExtraction:

    def test_computer_extraction(self):
        raw = {"Computer": "SERVER01.corp.local"}

        result = normalize_ad(raw)

        assert result["host"] == "SERVER01.corp.local"

    def test_hostname_field(self):
        raw = {"host": "HOST01"}

        result = normalize_ad(raw)

        assert result["host"] == "HOST01"

    def test_hostname_extraction(self):
        raw = {"hostname": "HOSTNAME01"}

        result = normalize_ad(raw)

        assert result["host"] == "HOSTNAME01"


class TestADEventDescription:

    def test_message_used_as_description(self):
        raw = {"Message": "Test message"}

        result = normalize_ad(raw)

        assert "Test message" in result["description"]

    def test_failure_reason_used(self):
        raw = {"FailureReason": "Bad password"}

        result = normalize_ad(raw)

        assert "Bad password" in result["description"]

    def test_event_id_in_description(self):
        raw = {"EventID": 4624, "TargetUserName": "testuser"}

        result = normalize_ad(raw)

        assert "4624" in result["description"]
