"""Normalizer unit checks that protect the common schema.

The main normalization paths are exercised end-to-end through sample ingestion.
This test keeps the important ingestion security boundary: a tenant supplied by
the sender inside ``raw`` must never override the tenant assigned by the API key.
"""

from app.parsers.firewall import normalize_firewall
from app.schemas.normalized_event import Source


def test_tenant_cannot_be_overridden_from_raw_payload():
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
    assert event.source == Source.firewall
    assert event.event_type == "firewall_deny"
    assert event.src_ip == "10.0.1.10"
