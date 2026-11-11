"""Webhook URL validation with SSRF protection.

Validates outbound webhook destination URLs to prevent Server-Side Request
Forgery (SSRF) attacks. Checks are performed at both configuration time
(when a webhook URL is stored) and delivery time (immediately before an
HTTP request is made), with connection-time address consistency verification
to defend against DNS rebinding / time-of-check-time-of-use attacks.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Cloud metadata endpoints that must never be reachable from webhook delivery.
CLOUD_METADATA_HOSTS = {
    "169.254.169.254",  # AWS / Azure / GCP metadata
    "metadata.google.internal",  # GCP metadata
    "metadata.aws.internal",  # IMDSv2
}

# Common metadata IP ranges (IPv4).
METADATA_IPV4_NETS = [
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / metadata
]

# Docker Compose bridge network range - allowed for local development
# where webhook receivers run on the same Docker network as the backend.
# In production, webhook URLs should use public HTTPS endpoints.
DOCKER_NETWORK_NETS = [
    ipaddress.ip_network("172.16.0.0/12"),  # Docker default bridge network range
]

# Local-only webhook ports used by the self-hosted demo receiver. Production
# destinations must use standard web ports.
LOCAL_WEBHOOK_PORTS = {8000, 8008, 8080, 8443}


def _local_destinations_allowed() -> bool:
    """Local Docker receivers are only trusted outside production.

    The hosted service must never be able to reach private/bridge addresses,
    even if an administrator configures a malicious webhook URL.
    """
    from app.core.config import get_settings

    return get_settings().APP_ENV != "production"

# Common metadata hostnames (in addition to IP addresses).
METADATA_HOSTNAMES = {
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.aws.internal",
    "instance-data",
    "local-instance",
}


class WebhookUrlError(ValueError):
    """Raised when a webhook URL fails SSRF validation."""


def _is_private_or_reserved_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if an IP address is private, loopback, link-local,
    multicast, reserved, or unspecified."""
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return True
    if ip.is_unspecified or ip.is_reserved:
        return True
    # IPv4-mapped IPv6 addresses (::ffff:0:0/96) - check the embedded IPv4.
    if ip.version == 6 and ip.ipv4_mapped is not None:
        return _is_private_or_reserved_ip(ip.ipv4_mapped)
    return False


def _validate_host(host: str, port: Optional[int] = None) -> None:
    """Validate a hostname/IP address against SSRF rules.

    Resolves the hostname via getaddrinfo and validates every returned
    address. This defends against DNS rebinding where a hostname resolves
    to a public address at validation time but a private address at
    connection time.
    """
    if not host:
        raise WebhookUrlError("missing host")

    # Reject URL credentials (user:password@host).
    if "@" in host:
        raise WebhookUrlError("URL credentials not allowed")

    # Reject bare IPv6 literal addresses not enclosed in brackets.
    if host.startswith("[") and not host.endswith("]"):
        raise WebhookUrlError("invalid IPv6 literal")

    # Check if host is a literal IP address.
    try:
        ip = ipaddress.ip_address(host)
        if _is_private_or_reserved_ip(ip):
            raise WebhookUrlError(f"private or reserved IP address: {host}")
        return
    except ValueError:
        pass  # Not a literal IP; treat as hostname.

    # Reject known metadata hostnames.
    host_lower = host.lower()
    if host_lower in METADATA_HOSTNAMES:
        raise WebhookUrlError(f"metadata endpoint not allowed: {host}")

    # Reject hostnames that look like IP addresses (e.g. "169.254.169.254"
    # passed as a string). Already handled by ip_address above, but catch
    # any edge cases.
    try:
        ipaddress.ip_address(host_lower)
        raise WebhookUrlError(f"literal IP address not allowed: {host}")
    except ValueError:
        pass

    # Resolve the hostname and validate every address. This catches
    # DNS rebinding: even if one address is public, if any address is
    # private, the hostname is rejected.
    try:
        infos = socket.getaddrinfo(host, port or 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise WebhookUrlError(f"DNS resolution failed for {host}: {exc}") from exc

    if not infos:
        raise WebhookUrlError(f"no addresses resolved for {host}")

    seen_private = False
    for family, _type, _proto, _canon, sockaddr in infos:
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_private_or_reserved_ip(ip):
            # Allow Docker Compose bridge network addresses for local
            # development. In production, webhook URLs should use public
            # HTTPS endpoints.
            if _local_destinations_allowed() and any(
                ip in net for net in DOCKER_NETWORK_NETS
            ):
                logger.warning(
                    "webhook host %s resolves to Docker bridge address %s; allowing for local development",
                    host,
                    addr,
                )
                continue
            seen_private = True
            logger.warning(
                "webhook host %s resolves to private address %s; rejecting",
                host,
                addr,
            )

    if seen_private:
        raise WebhookUrlError(
            f"host {host} resolves to a private or reserved address"
        )


def validate_webhook_url(url: str) -> str:
    """Validate a webhook destination URL against SSRF rules.

    Returns the normalized URL if valid. Raises WebhookUrlError otherwise.
    """
    if not url or not isinstance(url, str):
        raise WebhookUrlError("webhook URL is required")

    url = url.strip()
    if not url:
        raise WebhookUrlError("webhook URL is required")

    parsed = urlparse(url)

    # Only http and https schemes are allowed.
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise WebhookUrlError(f"unsupported scheme: {scheme or '(none)'}")

    # Reject URL credentials (user:password@host).
    if parsed.username or parsed.password:
        raise WebhookUrlError("URL credentials not allowed")

    host = parsed.hostname
    if not host:
        raise WebhookUrlError("missing host")

    # Port validation: only standard web ports.
    port = parsed.port
    allowed_ports = {80, 443}
    if _local_destinations_allowed():
        allowed_ports |= LOCAL_WEBHOOK_PORTS
    if port is not None and port not in allowed_ports:
        raise WebhookUrlError(f"unsupported port: {port}")

    # Validate the host (includes DNS resolution and address consistency).
    _validate_host(host, port)

    return url


def is_safe_webhook_url(url: str) -> bool:
    """Return True if a webhook URL passes SSRF validation, False otherwise."""
    try:
        validate_webhook_url(url)
        return True
    except WebhookUrlError:
        return False
