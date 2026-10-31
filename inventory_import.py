"""Validate CSV inventory files and apply imports with traceable stock balances."""

from __future__ import annotations

import csv
import io
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from inventory_service import validate_component_form

CSV_COLUMNS = (
    "sku", "name", "description", "category", "supplier",
    "quantity", "reorder_level", "unit_price",
)
REQUIRED_COLUMNS = set(CSV_COLUMNS) - {"description"}
MAX_CSV_BYTES = 1024 * 1024
MAX_CSV_ROWS = 5000


@dataclass
class RowError:
    line: int
    sku: str
    message: str


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    errors: list[RowError] = field(default_factory=list)

    @property
    def imported(self) -> int:
        return self.created + self.updated

    @property
    def rejected(self) -> int:
        return len(self.errors)


def parse_inventory_csv(content: bytes) -> tuple[list[tuple[int, tuple[Any, ...]]], list[RowError]]:
    """Parse the entire file before writes; invalid records become row errors.

    Invalid headers, encoding, limits or broken quoting reject the whole file,
    since record boundaries cannot be trusted in a malformed CSV document.
    """
    if len(content) > MAX_CSV_BYTES:
        raise ValueError("CSV file must be no larger than 1 MiB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV file must use UTF-8 encoding. Save it as CSV UTF-8 and try again.") from exc
    if "\x00" in text:
        raise ValueError("CSV file contains invalid null characters.")

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    records = []
    errors = []
    seen_skus = set()
    row_count = 0
    try:
        headers = next(reader, None)
        if not headers:
            raise ValueError("CSV file is empty. Include a header and at least one inventory record.")
        headers = [header.strip().lower().replace(" ", "_") for header in headers]
        if len(set(headers)) != len(headers):
            raise ValueError("CSV contains duplicate column names.")
        missing = REQUIRED_COLUMNS - set(headers)
        if missing:
            raise ValueError("Missing required columns: " + ", ".join(sorted(missing)) + ".")
        unknown = set(headers) - set(CSV_COLUMNS) - {"availability"}
        if unknown:
            raise ValueError("Unrecognized columns: " + ", ".join(sorted(unknown)) + ".")

        while True:
            line = reader.line_num + 1
            cells = next(reader, None)
            if cells is None:
                break
            if not any(cell.strip() for cell in cells):
                continue
            row_count += 1
            if row_count > MAX_CSV_ROWS:
                raise ValueError("CSV file must contain no more than 5,000 inventory records.")
            row = dict(zip(headers, cells))
            sku = row.get("sku", "").strip().upper()
            if len(cells) != len(headers):
                errors.append(RowError(line, sku, "Row must have the same number of fields as the header."))
                continue
            if sku in seen_skus:
                errors.append(RowError(line, sku, "Duplicate SKU in this file. Keep only one row per SKU."))
                continue
            if sku:
                seen_skus.add(sku)
            values, error = validate_component_form(row)
            if error:
                errors.append(RowError(line, sku, error))
            else:
                records.append((line, values))
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV near line {reader.line_num}. Check quoting and field lengths.") from exc

    if row_count == 0:
        raise ValueError("CSV file contains no inventory records.")
    return records, errors


def import_inventory_csv(db: sqlite3.Connection, *, user_id: int, content: bytes) -> ImportResult:
    records, errors = parse_inventory_csv(content)
    result = ImportResult(errors=errors)
    try:
        # Serialize with stock movements before reading balances or matching SKUs.
        db.execute("BEGIN IMMEDIATE")
        for line, values in records:
            sku, name, description, category, supplier, quantity, reorder_level, unit_price = values
            category_row = db.execute(
                "SELECT name FROM categories WHERE name = ? COLLATE NOCASE", (category,)
            ).fetchone()
            supplier_row = db.execute(
                "SELECT name FROM suppliers WHERE name = ? COLLATE NOCASE", (supplier,)
            ).fetchone()
            if category_row is None or supplier_row is None:
                missing = "category" if category_row is None else "supplier"
                result.errors.append(RowError(line, sku, f"Select a valid {missing} from the catalogue."))
                continue
            existing = db.execute("SELECT * FROM components WHERE sku = ?", (sku,)).fetchone()
            if existing is not None and existing["deleted_at"] is not None:
                result.errors.append(RowError(line, sku, "SKU belongs to a deleted component and cannot be reused."))
                continue

            # Store catalogue spelling so filters, renames and deletion checks agree.
            values = (sku, name, description, category_row["name"], supplier_row["name"],
                      quantity, reorder_level, unit_price)
            previous = int(existing["quantity"]) if existing is not None else 0
            if existing is None:
                cursor = db.execute(
                    """INSERT INTO components
                       (sku, name, description, category, supplier, quantity, reorder_level, unit_price)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", values,
                )
                component_id = cursor.lastrowid
                action = "created"
                result.created += 1
            else:
                component_id = existing["id"]
                db.execute(
                    """UPDATE components SET sku=?, name=?, description=?, category=?, supplier=?,
                       quantity=?, reorder_level=?, unit_price=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (*values, component_id),
                )
                action = "updated"
                result.updated += 1
            if quantity != previous:
                db.execute(
                    """INSERT INTO inventory_transactions
                       (component_id, user_id, transaction_type, quantity, previous_quantity, new_quantity, note)
                       VALUES (?, ?, 'adjustment', ?, ?, ?, ?)""",
                    (component_id, user_id, abs(quantity - previous), previous, quantity,
                     f"CSV inventory import, line {line}"),
                )
            db.execute(
                "INSERT INTO audit_log (user_id, event_type, details) VALUES (?, ?, ?)",
                (user_id, "component-imported",
                 f"{action} component_id={component_id}; sku={sku}; line={line}; quantity={previous}->{quantity}"),
            )
        result.errors.sort(key=lambda error: error.line)
        db.execute(
            "INSERT INTO audit_log (user_id, event_type, details) VALUES (?, ?, ?)",
            (user_id, "inventory-imported",
             f"created={result.created}; updated={result.updated}; rejected={result.rejected}"),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result
