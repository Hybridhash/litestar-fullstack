"""Rate-limit request identifier helpers.

Resolves the real client IP for rate-limiting when the application
sits behind a reverse proxy such as Cloudflare or Railway.
"""

from __future__ import annotations

from ipaddress import ip_address
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from ipaddress import IPv4Network, IPv6Network


def normalize_ip(value: str | None) -> str | None:
    """Extract and validate the first IP from a raw header value.

    Proxy headers like ``X-Forwarded-For`` may contain comma-separated
    lists (``"client, proxy1, proxy2"``).  This function takes the first
    entry, strips whitespace, and validates it as an IP address.

    Returns ``None`` for empty, missing, or unparsable values.
    """
    if not value:
        return None
    candidate = value.split(",", maxsplit=1)[0].strip()
    if not candidate:
        return None
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


def is_trusted_proxy(
    remote_ip: str | None,
    trusted_networks: tuple[IPv4Network | IPv6Network, ...],
) -> bool:
    """Return ``True`` if *remote_ip* belongs to one of the *trusted_networks*."""
    if not trusted_networks or not remote_ip:
        return False
    remote_ip_obj = ip_address(remote_ip)
    return any(remote_ip_obj in network for network in trusted_networks)


def create_rate_limit_identifier(
    *,
    trust_proxy_headers: bool,
    trusted_networks: tuple[IPv4Network | IPv6Network, ...],
) -> Callable[[object], str]:
    """Build a request → IP identifier function for :class:`RateLimitConfig`.

    The returned callable is passed directly to
    ``RateLimitConfig(identifier_for_request=...)``.
    """

    def _identifier(request: object) -> str:
        client = getattr(request, "client", None)
        remote_ip = normalize_ip(client.host if client else None)

        if trust_proxy_headers and is_trusted_proxy(remote_ip, trusted_networks):
            headers = getattr(request, "headers", {})
            cf_ip = normalize_ip(headers.get("CF-Connecting-IP"))
            if cf_ip:
                return cf_ip
            real_ip = normalize_ip(headers.get("X-Real-IP"))
            if real_ip:
                return real_ip

        return remote_ip or "unknown"

    return _identifier
