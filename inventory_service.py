"""Inventory business rules for the Electronics Store Inventory Management System."""

from __future__ import annotations

import math
import re
import sqlite3
from typing import Any, Literal

Availability = Literal["Out of Stock", "Low Stock", "In Stock"]


def validate_component_form(form) -> tuple[tuple[Any, ...] | None, str | None]:
    """Apply the same component and SKU rules to forms and CSV imports."""
    sku = form.get("sku", "").strip().upper()
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    category = form.get("category", "").strip()
    supplier = form.get("supplier", "").strip()
    try:
        quantity = int(form.get("quantity", ""))
        reorder_level = int(form.get("reorder_level", ""))
        unit_price = float(form.get("unit_price", "0"))
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
    if quantity > 2**63 - 1 or reorder_level > 2**63 - 1:
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

    try:
        db.execute("BEGIN IMMEDIATE")
        component = db.execute(
            "SELECT id, quantity FROM components WHERE id = ?", (component_id,)
        ).fetchone()
        if component is None:
            raise LookupError("component not found")

        previous = int(component["quantity"])
        new_quantity = previous + quantity if adjustment == "stock-in" else previous - quantity
        if new_quantity < 0:
            raise ValueError("stock-out quantity exceeds available stock")

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
            "INSERT INTO audit_log (user_id, event_type, details) VALUES (?, ?, ?)",
            (user_id, "stock-adjustment", f"{adjustment} component_id={component_id} quantity={quantity}; {previous}->{new_quantity}"),
        )
        db.commit()
        return previous, new_quantity
    except Exception:
        db.rollback()
        raise
