"""Shared validation for plain-text fields and SQLite-bound integers."""
from __future__ import annotations

import re

MAX_SQLITE_INTEGER = 2**63 - 1
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def text_value(value, label, maximum, *, required=False, multiline=False):
    """Normalize surrounding whitespace without interpreting HTML or SQL text."""
    if not isinstance(value, str) or CONTROL_CHARACTERS.search(value):
        raise ValueError(f"{label} must be text without control characters.")
    if not multiline and any(character in value for character in "\t\r\n"):
        raise ValueError(f"{label} must be a single line of text.")
    value = value.strip()
    if (required and not value) or len(value) > maximum:
        requirement = "is required and " if required else ""
        raise ValueError(f"{label} {requirement}must be {maximum} characters or fewer.")
    return value


def whole_number(value, label, *, minimum=0, maximum=MAX_SQLITE_INTEGER):
    """Accept ASCII decimal integers and check bounds before Python/SQLite conversion."""
    message = f"{label} must be a non-negative whole number within the supported range."
    if minimum == 1:
        message = f"{label} must be a whole number greater than zero within the supported range."
    if not isinstance(value, str):
        raise ValueError(message)
    value = value.strip()
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError(message)
    significant = value.lstrip("0") or "0"
    limit = str(maximum)
    if len(significant) > len(limit) or (len(significant) == len(limit) and significant > limit):
        raise ValueError(message)
    number = int(significant)
    if number < minimum:
        raise ValueError(message)
    return number


def account_values(form):
    """Validate web and CLI account fields; passwords are never stripped or echoed."""
    username = text_value(form.get("username", ""), "Username", 80, required=True)
    email = text_value(form.get("email", ""), "Email", 254, required=True)
    password = form.get("password", "")
    role = text_value(form.get("role", "Staff"), "Role", 5, required=True)
    if (not isinstance(password, str) or not 10 <= len(password) <= 1024 or "\x00" in password):
        raise ValueError("Password must contain between 10 and 1024 characters and no null characters.")
    if role not in ("Admin", "Staff"):
        raise ValueError("Select a valid role: Admin or Staff.")
    if email.count("@") != 1:
        raise ValueError("Enter a valid email address.")
    local, domain = email.rsplit("@", 1)
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Enter a valid email address.") from exc
    if (not local or len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local
            or re.search(r'[\s<>(),;:\\"\[\]]', local)
            or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*", domain)):
        raise ValueError("Enter a valid email address.")
    return username, email, password, role
