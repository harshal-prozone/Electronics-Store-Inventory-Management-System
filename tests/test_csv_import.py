import csv
import io
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import create_app
from inventory_import import CSV_COLUMNS, MAX_CSV_BYTES, import_inventory_csv
from inventory_service import adjust_stock


@pytest.fixture()
def app(tmp_path):
    return create_app({
        "TESTING": True, "WTF_CSRF_ENABLED": False, "SECRET_KEY": "csv-test-only",
        "DATABASE": str(tmp_path / "csv-inventory.sqlite"),
    })


@pytest.fixture()
def client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
    return client


def record(**overrides):
    return {
        "sku": "IMPORT-001", "name": "Imported board", "description": "CSV component",
        "category": "Microcontrollers", "supplier": "Maker Supplies",
        "quantity": "7", "reorder_level": "5", "unit_price": "12.50", **overrides,
    }


def csv_bytes(*records, headers=CSV_COLUMNS):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue().encode("utf-8")


def upload(client, content, filename="inventory.csv", **fields):
    return client.post("/components/import", data={"file": (io.BytesIO(content), filename), **fields})


def snapshot(app):
    with sqlite3.connect(app.config["DATABASE"]) as db:
        return [db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
                for table in ("components", "inventory_transactions", "audit_log")]


def test_import_creates_updates_and_records_balances(client, app):
    response = upload(client, csv_bytes(
        record(sku=" import-001 ", category="microCONTROLLERS", supplier="maker supplies"),
        record(sku="mcu-ard-001", name="Updated Arduino", quantity="2", unit_price="19.999"),
        record(sku="IMPORT-ZERO", quantity="0"),
    ))
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "3 imported" in page and "2 created, 1 updated" in page and "0 rejected" in page
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM components").fetchone()[0] == 6
        assert db.execute("SELECT category, supplier, quantity FROM components WHERE sku='IMPORT-001'").fetchone() == (
            "Microcontrollers", "Maker Supplies", 7,
        )
        assert db.execute("SELECT id, name, quantity, unit_price FROM components WHERE sku='MCU-ARD-001'").fetchone() == (
            1, "Updated Arduino", 2, 20.0,
        )
        assert db.execute("""SELECT transaction_type, quantity, previous_quantity, new_quantity, user_id
                             FROM inventory_transactions ORDER BY id""").fetchall() == [
            ("adjustment", 7, 0, 7, 1), ("adjustment", 10, 12, 2, 1),
        ]
        assert db.execute("SELECT COUNT(*) FROM audit_log WHERE event_type='component-imported'").fetchone()[0] == 3
        assert db.execute("SELECT details FROM audit_log WHERE event_type='inventory-imported'").fetchone()[0] == (
            "created=2; updated=1; rejected=0"
        )
    assert "CSV inventory import, line 3" in client.get("/components/1").get_data(as_text=True)
    assert "Updated Arduino" in client.get("/components?status=Low+Stock").get_data(as_text=True)


def test_import_repeat_does_not_duplicate_components_or_stock_history(client, app):
    content = csv_bytes(record())
    upload(client, content)
    response = upload(client, content)
    assert "0 created, 1 updated" in response.get_data(as_text=True)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM components WHERE sku='IMPORT-001'").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM inventory_transactions").fetchone()[0] == 1


def test_mixed_rows_report_lines_and_leave_rejected_inventory_unchanged(client, app):
    response = upload(client, csv_bytes(
        record(description="Quoted comma, and\nsecond line"),
        record(sku="BAD-NUMBER", quantity="1.5"),
        record(sku=" import-001 ", quantity="100"),
        record(sku="MCU-ARD-001", category="Unknown category", quantity="0"),
        record(sku="BAD-SUPPLIER", supplier="Unknown supplier"),
        record(sku="IMPORT-002"),
    ))
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "2 imported" in page and "4 rejected" in page
    for line in (4, 5, 6, 7):
        assert f"<td>{line}</td>" in page
    for message in ("whole numbers", "Duplicate SKU", "valid category", "valid supplier"):
        assert message in page
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM components").fetchone()[0] == 6
        assert db.execute("SELECT quantity FROM components WHERE sku='MCU-ARD-001'").fetchone()[0] == 12
        assert db.execute("SELECT quantity, description FROM components WHERE sku='IMPORT-001'").fetchone() == (
            7, "Quoted comma, and\nsecond line",
        )


@pytest.mark.parametrize("overrides, message", [
    ({"sku": ""}, "SKU is required"),
    ({"sku": "invalid sku"}, "SKU is required"),
    ({"sku": "A" * 41}, "SKU is required"),
    ({"name": ""}, "Component name is required"),
    ({"name": "A" * 121}, "Component name is required"),
    ({"description": "A" * 1001}, "exceeds the allowed length"),
    ({"quantity": ""}, "whole numbers"),
    ({"quantity": "3.5"}, "whole numbers"),
    ({"quantity": "-1"}, "non-negative finite"),
    ({"quantity": "9223372036854775808"}, "at most 9223372036854775807"),
    ({"reorder_level": "NaN"}, "whole numbers"),
    ({"reorder_level": "-1"}, "non-negative finite"),
    ({"reorder_level": "9" * 100}, "at most 9223372036854775807"),
    ({"unit_price": ""}, "price must be numeric"),
    ({"unit_price": "twelve"}, "price must be numeric"),
    ({"unit_price": "-0.01"}, "non-negative finite"),
    ({"unit_price": "NaN"}, "non-negative finite"),
    ({"unit_price": "inf"}, "non-negative finite"),
    ({"unit_price": "1e309"}, "non-negative finite"),
    ({"category": ""}, "valid category"),
    ({"supplier": ""}, "valid supplier"),
])
def test_invalid_values_are_rejected_without_writing_components(client, app, overrides, message):
    before = snapshot(app)
    response = upload(client, csv_bytes(record(**overrides)))
    page = response.get_data(as_text=True)
    assert "0 imported" in page and "1 rejected" in page and message in page
    assert snapshot(app)[:2] == before[:2]


def test_deleted_skus_stay_reserved_and_invalid_first_duplicates_are_rejected(client, app):
    with sqlite3.connect(app.config["DATABASE"]) as db:
        db.execute("UPDATE components SET deleted_at=CURRENT_TIMESTAMP WHERE id=1")
    response = upload(client, csv_bytes(
        record(sku="mcu-ard-001"), record(name=""), record(sku="import-001"),
    ))
    page = response.get_data(as_text=True)
    assert "0 imported" in page and "3 rejected" in page
    assert "deleted component" in page and "Duplicate SKU" in page
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM components").fetchone()[0] == 4
        assert db.execute("SELECT quantity, deleted_at IS NOT NULL FROM components WHERE id=1").fetchone() == (12, 1)


def test_export_headers_bom_reordered_columns_and_blank_lines(client, app):
    headers = [" Unit Price ", "Quantity", "Reorder Level", "Supplier", "Category", "Name", "SKU", "Availability"]
    row = dict(zip(headers, ["0", "0", "0", "Maker Supplies", "Microcontrollers", "Caf\u00e9 board", "IMPORT-001", "In Stock"]))
    content = b"\xef\xbb\xbf" + csv_bytes(row, headers=headers) + b"\r\n,,,,,,,\r\n"
    response = upload(client, content, filename="Inventory.CSV")
    assert "1 imported" in response.get_data(as_text=True)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT name, description, quantity FROM components WHERE sku='IMPORT-001'").fetchone() == (
            "Caf\u00e9 board", "", 0,
        )
    exported = client.get("/export/components.csv")
    response = upload(client, exported.data)
    assert "0 created, 5 updated" in response.get_data(as_text=True)


def test_short_and_extra_rows_are_rejected_and_later_valid_rows_import(client, app):
    content = csv_bytes(record()) + b"SHORT,Only two fields\r\n" + b"EXTRA,x,x,x,x,0,0,0,extra\r\n"
    content += csv_bytes(record(sku="IMPORT-002")).split(b"\r\n", 1)[1]
    response = upload(client, content)
    page = response.get_data(as_text=True)
    assert "2 imported" in page and "2 rejected" in page
    assert page.count("Row must have the same number of fields") == 2


@pytest.mark.parametrize("content, message", [
    (b"", "CSV file is empty"),
    (csv_bytes(), "contains no inventory records"),
    (b"sku,name\nX,Board\n", "Missing required columns"),
    (csv_bytes(record()).replace(b"sku,name", b"sku,SKU"), "duplicate column names"),
    (csv_bytes(record()).replace(b"description", b"unexpected"), "Unrecognized columns"),
    (csv_bytes(record()) + b'"unclosed field', "Malformed CSV"),
    (csv_bytes(record()) + b'"bad"quote,rest\n', "Malformed CSV"),
    (csv_bytes(record()) + b"\xff", "UTF-8 encoding"),
    (csv_bytes(record()) + b"\x00", "invalid null characters"),
    (b"A" * (MAX_CSV_BYTES + 1), "no larger than 1 MiB"),
], ids=["empty", "header-only", "missing-columns", "duplicate-columns", "unknown-column",
        "unclosed-quote", "bad-quote", "invalid-encoding", "null-byte", "oversized-file"])
def test_bad_files_reject_everything_before_writes(client, app, content, message):
    before = snapshot(app)
    response = upload(client, content)
    assert response.status_code == 400
    assert message in response.get_data(as_text=True)
    assert snapshot(app) == before


def test_record_and_request_limits_reject_without_writes(client, app):
    before = snapshot(app)
    response = upload(client, csv_bytes(*(record(sku=f"BULK-{i}") for i in range(5001))))
    assert response.status_code == 400
    assert "no more than 5,000" in response.get_data(as_text=True)
    # CSRF's form parsing can encounter the request limit before user loading.
    app.config["WTF_CSRF_ENABLED"] = True
    response = upload(client, b"x" * (2 * MAX_CSV_BYTES + 1))
    assert response.status_code == 413
    assert "Upload is too large" in response.get_data(as_text=True)
    assert snapshot(app) == before


def test_missing_file_wrong_extension_and_template(client, app):
    before = snapshot(app)
    assert client.post("/components/import").status_code == 400
    assert upload(client, csv_bytes(record()), filename="").status_code == 400
    assert upload(client, csv_bytes(record()), filename="inventory.txt").status_code == 400
    response = client.get("/components/import/template.csv")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    assert next(csv.reader(io.StringIO(response.get_data(as_text=True)))) == list(CSV_COLUMNS)
    assert snapshot(app) == before


def test_admin_only_pages_upload_and_template(client, app):
    assert 'href="/components/import"' in client.get("/components").get_data(as_text=True)
    anonymous = app.test_client()
    for path in ("/components/import", "/components/import/template.csv"):
        assert anonymous.get(path).status_code == 302
    assert upload(anonymous, csv_bytes(record())).status_code == 302
    with sqlite3.connect(app.config["DATABASE"]) as db:
        db.execute("INSERT INTO users (username,email,password_hash,role) VALUES ('staff','staff@example.test','unused','Staff')")
        staff_id = db.execute("SELECT id FROM users WHERE username='staff'").fetchone()[0]
    with client.session_transaction() as session:
        session["user_id"] = staff_id
    before = snapshot(app)
    for path in ("/components/import", "/components/import/template.csv"):
        assert client.get(path).status_code == 403
    assert upload(client, csv_bytes(record())).status_code == 403
    assert 'href="/components/import"' not in client.get("/components").get_data(as_text=True)
    assert snapshot(app) == before


def test_upload_requires_valid_csrf_token(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    before = snapshot(app)
    assert upload(client, csv_bytes(record())).status_code == 400
    assert upload(client, csv_bytes(record()), csrf_token="invalid").status_code == 400
    assert snapshot(app) == before
    page = client.get("/components/import").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    response = upload(client, csv_bytes(record()), csrf_token=token)
    assert response.status_code == 200 and "1 imported" in response.get_data(as_text=True)


def test_report_escapes_untrusted_sku_and_header(client):
    response = upload(client, csv_bytes(record(sku="<script>alert(1)</script>")))
    assert "<script>alert(1)</script>" not in response.get_data(as_text=True)
    assert "&lt;SCRIPT&gt;" in response.get_data(as_text=True)
    response = upload(client, csv_bytes(record()).replace(b"description", b"<script>alert(1)</script>"))
    assert "<script>alert(1)</script>" not in response.get_data(as_text=True)


@pytest.mark.parametrize("table, condition", [
    ("inventory_transactions", "NEW.new_quantity = 9"),
    ("audit_log", "NEW.details LIKE '%IMPORT-FAIL%'"),
])
def test_database_failure_rolls_back_components_history_and_audit(client, app, table, condition):
    with sqlite3.connect(app.config["DATABASE"]) as db:
        db.execute(f"""CREATE TRIGGER fail_csv BEFORE INSERT ON {table}
                       WHEN {condition} BEGIN SELECT RAISE(ABORT, 'simulated import failure'); END""")
    before = snapshot(app)
    response = upload(client, csv_bytes(record(sku="MCU-ARD-001"), record(sku="IMPORT-FAIL", quantity="9")))
    assert response.status_code == 503
    assert "No records were imported" in response.get_data(as_text=True)
    assert snapshot(app) == before


def test_import_serializes_with_stock_movements(app):
    barrier = threading.Barrier(2)

    def update(importing):
        with sqlite3.connect(app.config["DATABASE"], timeout=10) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            barrier.wait(timeout=5)
            if importing:
                return import_inventory_csv(db, user_id=1, content=csv_bytes(record(sku="MCU-ARD-001", quantity="3")))
            return adjust_stock(db, component_id=1, user_id=1, adjustment="stock-in", quantity=1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(update, importing) for importing in (True, False)]
        for future in futures:
            future.result(timeout=15)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        movements = db.execute("SELECT previous_quantity,new_quantity FROM inventory_transactions ORDER BY id").fetchall()
        assert len(movements) == 2
        assert movements[0][0] == 12
        assert movements[0][1] == movements[1][0]
        assert db.execute("SELECT quantity FROM components WHERE id=1").fetchone()[0] == movements[1][1]
