"""Validate the network peer address recorded in audit events."""
from ipaddress import ip_address


def normalize_audit_ip(value: str | None) -> str | None:
    """Return a canonical IPv4/IPv6 address, or None for absent/invalid peers.

    No proxy headers are consulted here.  A WSGI server's peer address can be a
    reverse proxy; identifying the originating client requires separately
    configured and trusted proxy handling at deployment time.
    """
    if not isinstance(value, str) or len(value) > 45 or "%" in value:
        return None
    try:
        return str(ip_address(value))
    except ValueError:
        return None
