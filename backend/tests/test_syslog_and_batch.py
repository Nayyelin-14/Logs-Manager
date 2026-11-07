"""Unit tests for syslog parsing, batch parsing, and source resolution."""

import pytest

from app.core.exceptions import ValidationError
from app.integrations.syslog import (
    parse_key_values,
    parse_rfc3164_timestamp,
    parse_syslog_message,
)
from app.ingest.batch import (
    detect_format,
    looks_like_syslog_line,
    parse_batch_records,
    validate_upload,
)
from app.models.enums import Source
from app.parsers.canonical import infer_source_from_event
from app.services.ingest_service import resolve_source


class TestSyslogParsing:
    def test_rfc3164_line(self):
        line = "<34>Oct 11 22:14:15 mymachine su[1234]: 'su root' failed for lonvick"
        parsed = parse_syslog_message(line)
        assert parsed is not None
        assert parsed["priority"] == 34
        assert parsed["host"] == "mymachine"
        assert "failed for lonvick" in parsed["msg"]
        from datetime import datetime

        assert datetime.fromisoformat(parsed["timestamp"]) is not None

    def test_rfc5424_line(self):
        line = (
            "<165>1 2003-10-11T22:14:15.003Z mymachine.example.com su - "
            "ID47 - BOM'su root' failed for lonvick"
        )
        parsed = parse_syslog_message(line)
        assert parsed is not None
        assert parsed["priority"] == 165
        assert parsed["host"] == "mymachine.example.com"
        assert "failed for lonvick" in parsed["msg"]

    def test_key_value_extraction(self):
        fields = parse_key_values('user=alice src_ip=10.0.0.1 msg="login failed" reason=bad_password')
        assert fields["user"] == "alice"
        assert fields["src_ip"] == "10.0.0.1"
        assert fields["msg"] == "login failed"
        assert fields["reason"] == "bad_password"

    def test_rfc3164_timestamp(self):
        iso = parse_rfc3164_timestamp("Oct 11 22:14:15")
        assert iso is not None
        assert iso.endswith("22:14:15+00:00") or "22:14:15" in iso

    @staticmethod
    def _with_timezone(value):
        """Context manager: temporarily set SYSLOG_TIMEZONE."""
        from contextlib import contextmanager

        from app.core.config import get_settings

        @contextmanager
        def _ctx():
            settings = get_settings()
            original = settings.SYSLOG_TIMEZONE
            settings.SYSLOG_TIMEZONE = value
            try:
                yield
            finally:
                settings.SYSLOG_TIMEZONE = original

        return _ctx()

    def test_rfc3164_default_timezone_is_utc(self):
        with self._with_timezone("UTC"):
            iso = parse_rfc3164_timestamp("Oct 11 22:14:15")
            assert iso.endswith("22:14:15+00:00")

    def test_rfc3164_configurable_iana_timezone(self):
        with self._with_timezone("Asia/Bangkok"):
            iso = parse_rfc3164_timestamp("Oct 11 22:14:15")
            assert iso.endswith("22:14:15+07:00"), iso

    def test_rfc3164_local_timezone_matches_host_offset(self):
        from datetime import datetime as _dt, timezone as _tz

        local_offset = _dt.now(_tz.utc).astimezone().utcoffset()
        with self._with_timezone("local"):
            iso = parse_rfc3164_timestamp("Oct 11 22:14:15")
            parsed_dt = _dt.fromisoformat(iso)
            assert parsed_dt.hour == 22 and parsed_dt.minute == 14 and parsed_dt.second == 15
            assert parsed_dt.utcoffset() == local_offset

    def test_rfc3164_invalid_timezone_falls_back_to_utc(self):
        with self._with_timezone("Not/AZone"):
            iso = parse_rfc3164_timestamp("Oct 11 22:14:15")
            assert iso.endswith("22:14:15+00:00")

    def test_rfc5424_offset_is_untouched_by_timezone_policy(self):
        line = "<165>1 2003-10-11T22:14:15.003+05:30 mymachine.example.com su - ID47 - hi"
        with self._with_timezone("Asia/Bangkok"):
            parsed = parse_syslog_message(line)
            assert parsed["timestamp"].endswith("+05:30"), parsed["timestamp"]

    def test_empty_input_returns_none(self):
        assert parse_syslog_message("   ") is None

    def test_line_detection(self):
        assert looks_like_syslog_line("<134>1 2024-01-01T00:00:00Z host app - - - hi")
        assert looks_like_syslog_line("Oct 11 22:14:15 mymachine su: hi")
        assert not looks_like_syslog_line("just some plain text")


class TestBatchParsing:
    def test_detect_json(self):
        assert detect_format('[{"a": 1}]', "data", "") == "json"
        assert detect_format('{"a": 1}', "x", "application/json") == "json"
        assert detect_format('[{"a": 1}]', "export.txt", "") == "json"

    def test_detect_jsonl_by_extension(self):
        assert detect_format('{"a": 1}\n{"b": 2}', "x.jsonl", "") == "jsonl"

    def test_detect_csv(self):
        text = "a,b,c\n1,2,3\n"
        assert detect_format(text, "x", "text/csv") == "csv"
        assert detect_format(text, "data.csv", "") == "csv"

    def test_detect_syslog(self):
        text = "<34>Oct 11 22:14:15 host app: one\n<34>Oct 11 22:14:16 host app: two\n"
        assert detect_format(text, "syslog.log", "") == "syslog"

    def test_parse_jsonl_tolerates_bad_lines(self):
        text = '{"source": "api", "event_type": "ok"}\n{oops\n{"source": "api", "event_type": "ok2"}\n'
        events, rejected, fmt = parse_batch_records(text.encode(), "probe.jsonl", "")
        assert fmt == "jsonl"
        assert len(events) == 2
        assert len(rejected) == 1
        assert "Invalid JSON" in rejected[0]["error"]

    def test_parse_syslog_file(self):
        text = (
            "<34>Oct 11 22:14:15 fw01 filter: src=10.0.0.1 action=DENY\n"
            "<34>Oct 11 22:14:16 fw01 filter: src=10.0.0.2 action=DENY\n"
        )
        events, rejected, fmt = parse_batch_records(text.encode(), "fw.log", "")
        assert fmt == "syslog"
        assert len(events) == 2
        assert rejected == []
        assert events[0]["host"] == "fw01"

    def test_parse_json_array(self):
        text = '[{"source": "api", "event_type": "a"}, {"source": "api", "event_type": "b"}]'
        events, rejected, fmt = parse_batch_records(text.encode(), "probe.json", "")
        assert fmt == "json"
        assert len(events) == 2

    def test_empty_file_raises(self):
        with pytest.raises(ValidationError):
            parse_batch_records(b"", "empty.json", "application/json")

    def test_non_dict_json_entries_are_dropped(self):
        text = '[{"source": "api"}, "not-a-dict", 42]'
        events, _rejected, _fmt = parse_batch_records(text.encode(), "x.json", "")
        assert len(events) == 1


class TestUploadValidation:
    def test_allowed_extensions(self):
        for name in ("a.json", "b.jsonl", "c.csv", "d.log", "e.txt", "f.ndjson"):
            validate_upload(name, 10)

    def test_rejects_disallowed_extension(self):
        with pytest.raises(ValidationError, match="Unsupported file type"):
            validate_upload("malware.exe", 10)

    def test_rejects_missing_extension(self):
        with pytest.raises(ValidationError, match="extension"):
            validate_upload("noextension", 10)

    def test_rejects_empty_file(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_upload("a.json", 0)

    def test_rejects_oversized_file(self):
        from app.ingest.batch import MAX_FILE_BYTES

        with pytest.raises(ValidationError, match="byte upload limit"):
            validate_upload("a.json", MAX_FILE_BYTES + 1)


class TestSourceResolution:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("syslog", Source.FIREWALL),
            ("firewall", Source.FIREWALL),
            ("windows", Source.AD),
            ("active_directory", Source.AD),
            ("o365", Source.M365),
            ("office365", Source.M365),
            ("cloudtrail", Source.AWS),
            ("aws", Source.AWS),
            ("crowdstrike", Source.CROWDSTRIKE),
            ("api", Source.API),
            (Source.NETWORK, Source.NETWORK),
        ],
    )
    def test_aliases(self, value, expected):
        assert resolve_source(value) == expected

    def test_unsupported_source_raises(self):
        with pytest.raises(ValidationError, match="Unsupported source"):
            resolve_source("skynet")

    def test_infer_from_dict_event(self):
        # Regression: plain dicts used to raise AttributeError on `.raw`
        assert infer_source_from_event({"msg": "blocked", "src_ip": "10.0.0.1"}) == Source.FIREWALL
        assert resolve_source(None, {"src_ip": "10.0.0.1", "msg": "x"}) == Source.FIREWALL

    def test_infer_from_raw_wrapper(self):
        source = resolve_source(None, {"raw": {"msg": "denied"}, "tenant": "demoA"})
        assert isinstance(source, Source)
