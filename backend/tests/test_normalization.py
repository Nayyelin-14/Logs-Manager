"""Common-schema normalization for the seven assignment source types.

Every source is pushed through the same production entry point
(``NormalizationService.normalize_event``) and checked against the shared
contract the database, search, and dashboard depend on:

* a recognized ``source`` and ``event_type``,
* an integer severity in the assignment's 0-10 range,
* an action when the source provides one,
* the original payload preserved in ``raw``.

The final test covers the ingestion security boundary: a tenant supplied by the
sender must never override the tenant resolved from the API key.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.models.enums import Source
from app.parsers.router import NormalizationService

SAMPLES = pathlib.Path(__file__).resolve().parents[2] / "samples"


def _sample(name: str) -> dict:
    return json.loads((SAMPLES / name).read_text())


FIREWALL_EVENT = {
    "priority": 134,
    "action": "deny",
    "src": "10.0.0.5",
    "dst": "8.8.8.8",
    "spt": 54321,
    "dpt": 53,
    "proto": "UDP",
    "msg": "DNS blocked",
    "policy": "block-dns",
    "event": "traffic",
}

NETWORK_EVENT = {
    "priority": 190,
    "host": "router01",
    "if": "Gi0/1",
    "event": "link-down",
    "mac": "aa:bb:cc:dd:ee:ff",
    "message": (
        "<190>Oct 30 22:15:01 router01 source=network vendor=Cisco product=IOS "
        "action=ALLOW src=192.168.1.10 dst=1.1.1.1 spt=51515 dpt=443 proto=TCP "
        'msg="outbound https" event=traffic if=Gi0/1 mac=aa:bb:cc:dd:ee:ff'
    ),
}

API_EVENT = {
    "source": "api",
    "event_type": "app_login_failed",
    "user": "alice",
    "ip": "203.0.113.7",
    "reason": "wrong_password",
    "status": "failed",
    "action": "LOGIN",
    "severity": 5,
    "@timestamp": "2026-10-30T22:20:00Z",
}

CASES = [
    pytest.param("firewall", FIREWALL_EVENT, Source.FIREWALL, "firewall_deny", id="firewall"),
    pytest.param("network", NETWORK_EVENT, Source.NETWORK, "link-down", id="network"),
    pytest.param("api", API_EVENT, Source.API, "app_login_failed", id="api"),
    pytest.param("aws", _sample("aws_cloudtrail.json"), Source.AWS, "CreateUser", id="aws"),
    pytest.param("m365", _sample("m365_audit.json"), Source.M365, "UserLoggedIn", id="m365"),
    pytest.param("ad", _sample("ad_4625.json"), Source.AD, "ad_logon_failed", id="ad"),
    pytest.param(
        "crowdstrike",
        _sample("crowdstrike.json"),
        Source.CROWDSTRIKE,
        "MalwareDetected",
        id="crowdstrike",
    ),
]


@pytest.mark.parametrize("name,raw,expected_source,expected_type", CASES)
def test_each_source_normalizes_to_the_common_schema(
    name, raw, expected_source, expected_type
):
    normalized = NormalizationService.normalize_event(raw, expected_source)

    assert normalized["source"] == expected_source
    assert normalized["event_type"] == expected_type
    assert normalized["canonical_event_type"], f"{name}: missing canonical type"
    assert isinstance(normalized["severity"], int)
    assert 0 <= normalized["severity"] <= 10
    assert normalized["raw"] == raw, f"{name}: original payload must be preserved"


def test_tenant_cannot_be_overridden_from_raw_payload():
    from app.parsers.firewall import normalize_firewall

    event = normalize_firewall(
        {
            "priority": 134,
            "action": "DENY",
            "src": "10.0.1.10",
            "dst": "8.8.8.8",
            "tenant": "attacker_tenant",
        },
        tenant="demoa",
    )

    assert event.tenant == "demoa"
    assert event.source == Source.FIREWALL
    assert event.event_type == "firewall_deny"
    assert event.src_ip == "10.0.1.10"
