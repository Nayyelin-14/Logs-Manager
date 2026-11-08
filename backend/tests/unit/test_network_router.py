import pytest

from app.parsers.structured import normalize_network
from app.models.enums import Source


class TestNetworkRouterBasic:

    def test_normalize_with_src_dst(self):
        raw = {
            "host": "router01",
            "vendor": "Cisco",
            "product": "IOS",
            "src": "192.168.1.10",
            "dst": "1.1.1.1",
            "spt": 51515,
            "dpt": 443,
            "proto": "TCP",
        }

        result = normalize_network(raw)

        assert result["source"] == Source.NETWORK
        assert result["host"] == "router01"
        assert result["vendor"] == "Cisco"
        assert result["product"] == "IOS"
        assert result["src_ip"] == "192.168.1.10"
        assert result["dst_ip"] == "1.1.1.1"

    def test_raw_preserved(self):
        raw = {"priority": 134, "src": "10.0.0.1"}

        result = normalize_network(raw)

        assert result["raw"]["priority"] == 134


class TestNetworkRouterFirewallFields:

    def test_src_ip_extraction(self):
        raw = {"src": "192.168.1.100"}

        result = normalize_network(raw)

        assert result["src_ip"] == "192.168.1.100"

    def test_dst_ip_extraction(self):
        raw = {"dst": "10.0.0.50"}

        result = normalize_network(raw)

        assert result["dst_ip"] == "10.0.0.50"

    def test_src_port_extraction(self):
        raw = {"spt": 51515}

        result = normalize_network(raw)

        assert result["src_port"] == 51515

    def test_dst_port_extraction(self):
        raw = {"dpt": 443}

        result = normalize_network(raw)

        assert result["dst_port"] == 443


class TestNetworkRouterSyslogFields:

    def test_host_extraction(self):
        raw = {"host": "router01"}

        result = normalize_network(raw)

        assert result["host"] == "router01"

    def test_vendor_extraction(self):
        raw = {"vendor": "Cisco"}

        result = normalize_network(raw)

        assert result["vendor"] == "Cisco"

    def test_product_extraction(self):
        raw = {"product": "IOS"}

        result = normalize_network(raw)

        assert result["product"] == "IOS"


class TestNetworkRouterEdgeCases:

    def test_empty_event(self):
        raw = {}

        result = normalize_network(raw)

        assert result is not None
        assert "source" in result
        assert result["source"] == Source.NETWORK

    def test_missing_message(self):
        raw = {"src": "10.0.0.1"}

        result = normalize_network(raw)

        assert result["src_ip"] == "10.0.0.1"

    def test_non_syslog_message(self):
        raw = {"msg": "just a plain message", "src": "10.0.0.1"}

        result = normalize_network(raw)

        assert result["src_ip"] == "10.0.0.1"


class TestNetworkRouterWithSyslogMessage:

    def test_valid_syslog_message(self):
        raw = {
            "msg": "<190>Oct 30 22:15:01 router01 source=network vendor=Cisco product=IOS event=link-down if=Gi0/1",
        }

        result = normalize_network(raw)

        assert result["source"] == Source.NETWORK
        assert result["host"] == "router01"

    def test_sample_network_syslog(self):
        raw = {
            "priority": 190,
            "src": "192.168.1.10",
            "dst": "1.1.1.1",
            "spt": 51515,
            "dpt": 443,
            "proto": "TCP",
            "host": "router01",
            "vendor": "Cisco",
            "product": "IOS",
        }

        result = normalize_network(raw)

        assert result["src_ip"] == "192.168.1.10"
        assert result["dst_ip"] == "1.1.1.1"
        assert result["src_port"] == 51515
        assert result["dst_port"] == 443
