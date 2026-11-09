"""Inventory business rules for the Electronics Store Inventory Management System."""

from __future__ import annotations

import math
import re
import sqlite3
from typing import Any, Literal

from audit_address import normalize_audit_ip
from input_validation import CONTROL_CHARACTERS, MAX_SQLITE_INTEGER, text_value

Availability = Literal["Out of Stock", "Low Stock", "In Stock"]


def validate_component_form(form) -> tuple[tuple[Any, ...] | None, str | None]:
    """Apply the same component and SKU rules to forms and CSV imports."""
    fields = ("sku", "name", "description", "category", "supplier", "quantity", "reorder_level", "unit_price")
    for field in fields:
        raw = form.get(field, "")
        if not isinstance(raw, str) or CONTROL_CHARACTERS.search(raw):
            return None, "Component fields must be text without control characters."
        if field != "description" and any(character in raw for character in "\t\r\n"):
            return None, "Component fields other than description must be single-line values."
    sku = form.get("sku", "").strip().upper()
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    category = form.get("category", "").strip()
    supplier = form.get("supplier", "").strip()
    try:
        for field in ("quantity", "reorder_level"):
            raw = form.get(field, "").strip()
            if not re.fullmatch(r"-?[0-9]+", raw):
                raise ValueError("invalid integer")
            significant = raw.lstrip("-0") or "0"
            if len(significant) > 19:
                return None, "Quantity and reorder level must be at most 9223372036854775807."
        # Strip leading zeroes before int() so long decimal representations
        # cannot trip Python's integer-string conversion limit.
        raw_quantity = form.get("quantity", "").strip()
        raw_reorder = form.get("reorder_level", "").strip()
        quantity = int(("-" if raw_quantity.startswith("-") else "") + (raw_quantity.lstrip("-0") or "0"))
        reorder_level = int(("-" if raw_reorder.startswith("-") else "") + (raw_reorder.lstrip("-0") or "0"))
        raw_price = form.get("unit_price", "0").strip()
        special_float = raw_price.lower().lstrip("+-") in {"nan", "inf", "infinity"}
        if not special_float and not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", raw_price):
            raise ValueError("invalid price")
        unit_price = float(raw_price)
    except (TypeError, ValueError):
        return None, "Quantity and reorder level must be whole numbers, and price must be numeric."
    if not sku or len(sku) > 40 or not re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]*", sku):
        return None, "SKU is required and may contain letters, numbers, dots, underscores, slashes and hyphens."
    if not name or len(name) > 120:
        return None, "Component name is required and must be 120 characters or fewer."
    if len(description) > 1000 or len(category) > 80 or len(supplier) > 120:
        return None, "Description, category or supplier exceeds the allowed length."
    if quantity < 0 or reorder_level < 0 or not math.isfinite(unit_price) or unit_price < 0:
        return None, "Quantity, reorder level and price must be non-negative finite values."
    if quantity > MAX_SQLITE_INTEGER or reorder_level > MAX_SQLITE_INTEGER:
        return None, "Quantity and reorder level must be at most 9223372036854775807."
    return (sku, name, description, category, supplier, quantity, reorder_level, round(unit_price, 2)), None


def availability_status(quantity: int, reorder_level: int) -> Availability:
    """Return the availability label defined by Issue #11.

    Rules, in priority order:
    - Quantity zero is always Out of Stock.
    - Positive quantity less than or equal to the reorder level is Low Stock.
    - Quantity above the reorder level is In Stock.

    Negative values and non-integer inputs are invalid inventory data.
    """
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise TypeError("quantity must be an integer")
    if isinstance(reorder_level, bool) or not isinstance(reorder_level, int):
        raise TypeError("reorder_level must be an integer")
    if quantity < 0:
        raise ValueError("quantity cannot be negative")
    if reorder_level < 0:
        raise ValueError("reorder level cannot be negative")
    if quantity == 0:
        return "Out of Stock"
    if quantity <= reorder_level:
        return "Low Stock"
    return "In Stock"


def adjust_stock(
    db: sqlite3.Connection,
    *,
    component_id: int,
    user_id: int,
    adjustment: Literal["stock-in", "stock-out"],
    quantity: int,
    note: str = "",
    ip_address: str | None = None,
) -> tuple[int, int]:
    """Atomically change stock and record a matching transaction.

    SQLite's BEGIN IMMEDIATE obtains the write lock before reading the current
    stock, preventing two stock-out requests from both spending the same units.
    Returns (previous_quantity, new_quantity). The caller handles HTTP feedback.
    """
    if adjustment not in ("stock-in", "stock-out"):
        raise ValueError("adjustment must be 'stock-in' or 'stock-out'")
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise TypeError("adjustment quantity must be an integer")
    if quantity <= 0:
        raise ValueError("adjustment quantity must be greater than zero")
    if quantity > MAX_SQLITE_INTEGER:
        raise ValueError("adjustment quantity exceeds the supported range")
    note = text_value(note, "Stock note", 250, multiline=True)

    try:
        db.execute("BEGIN IMMEDIATE")
        component = db.execute(
            "SELECT id, quantity FROM components WHERE id = ? AND deleted_at IS NULL", (component_id,)
        ).fetchone()
        if component is None:
            raise LookupError("component not found")

        previous = int(component["quantity"])
        new_quantity = previous + quantity if adjustment == "stock-in" else previous - quantity
        if new_quantity < 0:
            raise ValueError("stock-out quantity exceeds available stock")
        if new_quantity > MAX_SQLITE_INTEGER:
            raise ValueError("resulting stock exceeds the supported range")

        db.execute(
            "UPDATE components SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_quantity, component_id),
        )
        db.execute(
            """INSERT INTO inventory_transactions
               (component_id, user_id, transaction_type, quantity,
                previous_quantity, new_quantity, note)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (component_id, user_id, adjustment, quantity, previous, new_quantity, note.strip()),
        )
        db.execute(
            "INSERT INTO audit_log (user_id, event_type, details, ip_address) VALUES (?, ?, ?, ?)",
            (user_id, "stock-adjustment", f"{adjustment} component_id={component_id} quantity={quantity}; {previous}->{new_quantity}", normalize_audit_ip(ip_address)),
        )
        db.commit()
        return previous, new_quantity
    except Exception:
        db.rollback()
        raise
