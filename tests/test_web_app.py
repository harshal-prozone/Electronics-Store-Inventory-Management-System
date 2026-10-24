import csv
import io
import sqlite3
from datetime import timedelta

import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-only-secret",
            "DATABASE": str(tmp_path / "test-inventory.sqlite"),
        }
    )
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def sign_in(client):
    return client.post(
        "/login",
        data={"identity": "admin", "password": "ChangeMe123!"},
        follow_redirects=True,
    )


def create_catalog_entry(client, category="Test Category", supplier="Test Supplier"):
    category_response = client.post("/categories/new", data={"name": category}, follow_redirects=True)
    supplier_response = client.post("/suppliers/new", data={"name": supplier}, follow_redirects=True)
    assert category_response.status_code == 200
    assert supplier_response.status_code == 200


def test_inventory_requires_login(client):
    response = client.get("/components")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_inventory_page_shows_seeded_availability(client):
    sign_in(client)
    response = client.get("/components")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Arduino Uno R3" in page
    assert "Low Stock" in page
    assert "Out of Stock" in page
    assert "In Stock" in page


def test_stock_out_updates_quantity_and_availability(client, app):
    sign_in(client)
    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        component = db.execute("SELECT id, quantity FROM components WHERE sku = ?", ("MCU-ARD-001",)).fetchone()
        component_id = component["id"]
        assert component["quantity"] == 12
        admin_id = db.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
        db.close()

    response = client.post(
        f"/components/{component_id}/stock",
        data={"adjustment": "stock-out", "quantity": "12", "note": "Boundary test"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Status: Out of Stock" in page
    assert "Out of Stock" in page

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        new_quantity = db.execute("SELECT quantity FROM components WHERE id = ?", (component_id,)).fetchone()[0]
        transaction_count = db.execute("SELECT COUNT(*) FROM inventory_transactions WHERE component_id = ?", (component_id,)).fetchone()[0]
        db.close()
    assert new_quantity == 0
    assert transaction_count == 1


def test_stock_out_cannot_make_quantity_negative(client, app):
    sign_in(client)
    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute("SELECT id FROM components WHERE sku = ?", ("MCU-ESP-032",)).fetchone()
        component_id = row[0]
        db.close()
    client.post(
        f"/components/{component_id}/stock",
        data={"adjustment": "stock-out", "quantity": "4", "note": "Over-issue attempt"},
        follow_redirects=True,
    )
    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        new_quantity = db.execute("SELECT quantity FROM components WHERE id = ?", (component_id,)).fetchone()[0]
        transactions = db.execute("SELECT COUNT(*) FROM inventory_transactions WHERE component_id = ?", (component_id,)).fetchone()[0]
        db.close()
    assert new_quantity == 3
    assert transactions == 0


def test_threshold_edit_recalculates_status(client, app):
    sign_in(client)
    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        component_id = db.execute("SELECT id FROM components WHERE sku = ?", ("MCU-ARD-001",)).fetchone()[0]
        db.close()
    response = client.post(
        f"/components/{component_id}/edit",
        data={
            "sku": "MCU-ARD-001", "name": "Arduino Uno R3", "description": "Test board",
            "category": "Microcontrollers", "supplier": "Maker Supplies",
            "quantity": "12", "reorder_level": "12", "unit_price": "650",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Low Stock" in response.get_data(as_text=True)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok"}


def test_search_is_parameterized_and_handles_special_characters(client):
    sign_in(client)
    response = client.get("/components?q=%25%27%20OR%201%3D1--")
    assert response.status_code == 200
    assert "Arduino Uno R3" not in response.get_data(as_text=True)

def test_admin_can_access_user_management(client):
    sign_in(client)

    response = client.get("/admin/users")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "User Management" in page
    assert "admin" in page


def test_admin_can_create_staff_user(client, app):
    sign_in(client)

    response = client.post(
        "/admin/users",
        data={
            "username": "newstaff",
            "email": "newstaff@example.com",
            "password": "SecureStaff123!",
            "role": "Staff",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "User account created successfully." in response.get_data(as_text=True)

    with app.app_context():
        from flask import current_app

        db = sqlite3.connect(current_app.config["DATABASE"])
        user = db.execute(
            "SELECT username, email, password_hash, role "
            "FROM users WHERE username = ?",
            ("newstaff",),
        ).fetchone()
        db.close()

    assert user is not None
    assert user[0] == "newstaff"
    assert user[1] == "newstaff@example.com"
    assert user[2] != "SecureStaff123!"
    assert user[3] == "Staff"



def test_duplicate_username_is_rejected(client, app):
    sign_in(client)


    response = client.post(
        "/admin/users",
        data={
            "username": "admin",
            "email": "different@example.com",
            "password": "SecureStaff123!",
            "role": "Staff",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "already registered" in response.get_data(as_text=True)

    with app.app_context():
        from flask import current_app

        db = sqlite3.connect(current_app.config["DATABASE"])
        count = db.execute(
            "SELECT COUNT(*) FROM users WHERE email = ?",
            ("different@example.com",),
        ).fetchone()[0]
        db.close()

    assert count == 0

def create_catalog_entry(client, category="Test Category", supplier="Test Supplier"):
    category_response = client.post(
        "/categories/new",
        data={"name": category},
        follow_redirects=True,
    )
    supplier_response = client.post(
        "/suppliers/new",
        data={"name": supplier},
        follow_redirects=True,
    )

    assert category_response.status_code == 200
    assert supplier_response.status_code == 200

def test_staff_cannot_access_user_management(client, app):
    from werkzeug.security import generate_password_hash

    with app.app_context():
        from flask import current_app

        db = sqlite3.connect(current_app.config["DATABASE"])
        db.execute(
            "INSERT INTO users (username, email, password_hash, role) "
            "VALUES (?, ?, ?, ?)",
            (
                "teststaff",
                "teststaff@example.com",
                generate_password_hash("SecureStaff123!"),
                "Staff",
            ),
        )
        db.commit()
        db.close()

    client.post(
        "/login",
        data={
            "identity": "teststaff",
            "password": "SecureStaff123!",
        },
    )

    response = client.get("/admin/users")

    assert response.status_code == 403

def test_edit_cannot_change_quantity_without_transaction(client, app):
    import sqlite3
    from flask import current_app

    sign_in(client)

    with app.app_context():
        db = sqlite3.connect(current_app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        component = db.execute(
            "SELECT * FROM components WHERE sku = ?",
            ("MCU-ARD-001",),
        ).fetchone()
        assert component is not None

        component_id = component["id"]
        original_quantity = component["quantity"]
        original_transactions = db.execute(
            "SELECT COUNT(*) FROM inventory_transactions WHERE component_id = ?",
            (component_id,),
        ).fetchone()[0]

        payload = {
            "sku": component["sku"],
            "name": component["name"],
            "description": component["description"] or "",
            "category": component["category"],
            "supplier": component["supplier"],
            "quantity": "999",
            "reorder_level": str(component["reorder_level"]),
            "unit_price": str(component["unit_price"]),
        }
        db.close()

    edit_page = client.get(f"/components/{component_id}/edit")
    assert edit_page.status_code == 200
    assert b"readonly" in edit_page.data

    response = client.post(
        f"/components/{component_id}/edit",
        data=payload,
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        db = sqlite3.connect(current_app.config["DATABASE"])
        new_quantity = db.execute(
            "SELECT quantity FROM components WHERE id = ?",
            (component_id,),
        ).fetchone()[0]
        new_transactions = db.execute(
            "SELECT COUNT(*) FROM inventory_transactions WHERE component_id = ?",
            (component_id,),
        ).fetchone()[0]
        db.close()

    assert new_quantity == original_quantity
    assert new_transactions == original_transactions

def test_admin_can_create_component(client, app):
    sign_in(client)
    create_catalog_entry(client)
    payload = {
        "sku": "TEST-NEW-001",
        "name": "Test New Component",
        "description": "CRUD regression test",
        "category": "Test Category",
        "supplier": "Test Supplier",
        "quantity": "7",
        "reorder_level": "3",
        "unit_price": "12.50",
    }

    response = client.post("/components/new", data=payload, follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT name, quantity, reorder_level, unit_price FROM components WHERE sku = ?",
            ("TEST-NEW-001",),
        ).fetchone()
        db.close()

    assert row is not None
    assert row[0] == "Test New Component"
    assert row[1] == 7
    assert row[2] == 3
    assert row[3] == 12.5

def test_duplicate_component_sku_is_rejected(client, app):
    sign_in(client)
    create_catalog_entry(client, category="Test", supplier="Test Supplier")
    response = client.post(
        "/components/new",
        data={
            "sku": "MCU-ARD-001",
            "name": "Duplicate Arduino",
            "description": "",
            "category": "Test",
            "supplier": "Test Supplier",
            "quantity": "1",
            "reorder_level": "1",
            "unit_price": "10",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "already exists" in response.get_data(as_text=True)

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        count = db.execute(
            "SELECT COUNT(*) FROM components WHERE sku = ?",
            ("MCU-ARD-001",),
        ).fetchone()[0]
        db.close()

    assert count == 1

def test_admin_can_edit_component_details(client, app):
    sign_in(client)

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT id, quantity FROM components WHERE sku = ?",
            ("MCU-ARD-001",),
        ).fetchone()
        db.close()

    component_id, original_quantity = row

    response = client.post(
        f"/components/{component_id}/edit",
        data={
            "sku": "MCU-ARD-001",
            "name": "Arduino Uno R3 Revised",
            "description": "Updated component details",
            "category": "Microcontrollers",
            "supplier": "Maker Supplies",
            "quantity": str(original_quantity),
            "reorder_level": "8",
            "unit_price": "699.50",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT name, quantity, reorder_level, unit_price FROM components WHERE id = ?",
            (component_id,),
        ).fetchone()
        db.close()

    assert row[0] == "Arduino Uno R3 Revised"
    assert row[1] == original_quantity
    assert row[2] == 8
    assert row[3] == 699.5

def test_soft_deleted_component_is_hidden_from_inventory_and_csv(client, app):
    sign_in(client)

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT id FROM components WHERE sku = ?",
            ("MCU-ESP-032",),
        ).fetchone()
        db.close()

    component_id = row[0]
    response = client.post(
        f"/components/{component_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200

    inventory_page = client.get("/components").get_data(as_text=True)
    assert "ESP32 DevKit" not in inventory_page
    assert client.get(f"/components/{component_id}").status_code == 404

    export = client.get("/export/components.csv")
    assert export.status_code == 200
    csv_text = export.get_data(as_text=True)
    assert "Arduino Uno R3" in csv_text
    assert "ESP32 DevKit" not in csv_text

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT deleted_at FROM components WHERE id = ?",
            (component_id,),
        ).fetchone()
        db.close()

    assert row[0] is not None

def test_staff_cannot_create_edit_or_delete_components(client, app):
    from flask import current_app
    from werkzeug.security import generate_password_hash

    with app.app_context():
        db = sqlite3.connect(current_app.config["DATABASE"])
        db.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (
                "crudstaff",
                "crudstaff@example.com",
                generate_password_hash("SecureStaff123!"),
                "Staff",
            ),
        )
        component_id = db.execute(
            "SELECT id FROM components WHERE sku = ?",
            ("MCU-ARD-001",),
        ).fetchone()[0]
        db.commit()
        db.close()

    client.post(
        "/login",
        data={"identity": "crudstaff", "password": "SecureStaff123!"},
        follow_redirects=True,
    )

    payload = {
        "sku": "STAFF-UNAUTH-001",
        "name": "Unauthorized Component",
        "description": "",
        "category": "Test",
        "supplier": "Test Supplier",
        "quantity": "1",
        "reorder_level": "1",
        "unit_price": "10",
    }

    assert client.get("/components/new").status_code == 403
    assert client.get(f"/components/{component_id}/edit").status_code == 403
    assert client.post("/components/new", data=payload).status_code == 403
    assert client.post(f"/components/{component_id}/edit", data=payload).status_code == 403
    assert client.post(f"/components/{component_id}/delete").status_code == 403

    with app.app_context():
        db = sqlite3.connect(current_app.config["DATABASE"])
        new_count = db.execute(
            "SELECT COUNT(*) FROM components WHERE sku = ?",
            ("STAFF-UNAUTH-001",),
        ).fetchone()[0]
        original = db.execute(
            "SELECT name, deleted_at FROM components WHERE id = ?",
            (component_id,),
        ).fetchone()
        db.close()

    assert new_count == 0
    assert original[0] == "Arduino Uno R3"
    assert original[1] is None

def test_availability_report_filters_by_category_supplier_and_status(client):
    sign_in(client)
    response = client.get(
        "/reports/availability",
        query_string={
            "category": "Microcontrollers",
            "supplier": "Circuit Hub",
            "status": "Low Stock",
        },
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "ESP32 DevKit" in page
    assert "Arduino Uno R3" not in page
    assert "Raspberry Pi Pico" not in page
    assert "Low Stock" in page


def test_availability_report_csv_respects_status_filter(client):
    sign_in(client)
    response = client.get(
        "/reports/availability.csv",
        query_string={
            "category": "Microcontrollers",
            "supplier": "Circuit Hub",
            "status": "Low Stock",
        },
    )

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    report = response.get_data(as_text=True)
    assert "ESP32 DevKit" in report
    assert "Arduino Uno R3" not in report
    assert "Raspberry Pi Pico" not in report
    records = list(csv.DictReader(io.StringIO(report)))
    assert len(records) == 1
    assert records[0]["Component"] == "ESP32 DevKit"
    assert records[0]["Category"] == "Microcontrollers"
    assert records[0]["Supplier"] == "Circuit Hub"
    assert records[0]["Availability"] == "Low Stock"


def test_availability_report_pdf_is_valid_download(client):
    sign_in(client)
    response = client.get(
        "/reports/availability.pdf",
        query_string={
            "category": "Microcontrollers",
            "supplier": "Circuit Hub",
            "status": "Low Stock",
        },
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")
    assert "availability-report.pdf" in response.headers["Content-Disposition"]


def test_staff_cannot_access_availability_reports(client, app):
    from werkzeug.security import generate_password_hash

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        db.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (
                "reportstaff",
                "reportstaff@example.com",
                generate_password_hash("SecureStaff123!"),
                "Staff",
            ),
        )
        db.commit()
        db.close()

    client.post(
        "/login",
        data={"identity": "reportstaff", "password": "SecureStaff123!"},
    )

    assert client.get("/reports/availability").status_code == 403
    assert client.get("/reports/availability.csv").status_code == 403
    assert client.get("/reports/availability.pdf").status_code == 403


def test_login_accepts_email_address(client):
    response = client.post(
        "/login",
        data={"identity": "admin@example.local", "password": "ChangeMe123!"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/components")
    assert client.get("/components").status_code == 200


def test_permanent_session_expires(client, app):
    from flask import session

    sign_in(client)
    with client.session_transaction() as sess:
        assert sess.get("_permanent") is True
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=-1)
    response = client.get("/components")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_post_requires_csrf_token(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    response = client.post(
        "/login",
        data={"identity": "admin", "password": "ChangeMe123!"},
    )
    assert response.status_code == 400


def test_duplicate_email_is_rejected(client, app):
    sign_in(client)
    response = client.post(
        "/admin/users",
        data={
            "username": "different-user",
            "email": "admin@example.local",
            "password": "SecureStaff123!",
            "role": "Staff",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "already registered" in response.get_data(as_text=True)
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        count = db.execute(
            "SELECT COUNT(*) FROM users WHERE username = ?", ("different-user",)
        ).fetchone()[0]
        db.close()
    assert count == 0


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("sku", "SKU WITH SPACES"),
        ("name", "   "),
        ("quantity", "-1"),
        ("reorder_level", "-1"),
        ("unit_price", "-0.01"),
        ("unit_price", "nan"),
    ],
)
def test_component_creation_rejects_invalid_values(client, app, field, invalid_value):
    sign_in(client)
    create_catalog_entry(client, category="Validation", supplier="Test Supplier")
    payload = {
        "sku": "INVALID-INPUT-001",
        "name": "Validation test component",
        "description": "",
        "category": "Validation",
        "supplier": "Test Supplier",
        "quantity": "1",
        "reorder_level": "1",
        "unit_price": "12.50",
    }
    payload[field] = invalid_value
    response = client.post("/components/new", data=payload, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        count = db.execute(
            "SELECT COUNT(*) FROM components WHERE sku = ?", ("INVALID-INPUT-001",)
        ).fetchone()[0]
        db.close()
    assert count == 0


def test_csv_exports_escape_spreadsheet_formulas(client, app):
    sign_in(client)
    create_catalog_entry(client, category="+SUM(A1:A2)", supplier="@SUM(1,1)")
    payload = {
        "sku": "CSV-ESCAPE-001",
        "name": "=HYPERLINK(\"https://example.com\",\"click\")",
        "description": "\t=1+1",
        "category": "+SUM(A1:A2)",
        "supplier": "@SUM(1,1)",
        "quantity": "2",
        "reorder_level": "1",
        "unit_price": "12.50",
    }
    created = client.post("/components/new", data=payload, follow_redirects=True)
    assert created.status_code == 200

    # The form strips leading whitespace, so insert the tab-prefixed test
    # value directly to verify that the CSV exporter handles stored data.
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        db.execute(
            "UPDATE components SET description = ? WHERE sku = ?",
            ("\t=1+1", "CSV-ESCAPE-001"),
        )
        db.commit()
        db.close()

    catalogue_response = client.get("/export/components.csv")
    assert catalogue_response.status_code == 200
    catalogue_rows = list(csv.reader(io.StringIO(catalogue_response.get_data(as_text=True))))
    catalogue_record = next(row for row in catalogue_rows if row[0] == "CSV-ESCAPE-001")
    assert catalogue_record[1].startswith("'=")
    assert catalogue_record[2].startswith("'\t=")
    assert catalogue_record[3] == "'+SUM(A1:A2)"
    assert catalogue_record[4] == "'@SUM(1,1)"

    report_response = client.get(
        "/reports/availability.csv",
        query_string={"category": "+SUM(A1:A2)", "supplier": "@SUM(1,1)"},
    )
    assert report_response.status_code == 200
    report_rows = list(csv.DictReader(io.StringIO(report_response.get_data(as_text=True))))
    assert len(report_rows) == 1
    assert report_rows[0]["Component"].startswith("'=")
    assert report_rows[0]["Category"] == "'+SUM(A1:A2)"
    assert report_rows[0]["Supplier"] == "'@SUM(1,1)"


def test_non_testing_database_does_not_seed_a_known_default_password(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    application = create_app({"DATABASE": str(tmp_path / "no-default-admin.sqlite")})
    with application.app_context():
        db = sqlite3.connect(application.config["DATABASE"])
        count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        db.close()
    assert count == 0


def test_production_requires_explicit_secret_key(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
        create_app({"DATABASE": str(tmp_path / "production.sqlite")})



# Category and supplier catalogue regression tests.
def test_admin_can_create_and_edit_category(client, app):
    sign_in(client)

    response = client.post(
        "/categories/new",
        data={"name": "Test Electronics"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT id FROM categories WHERE name = ?",
            ("Test Electronics",),
        ).fetchone()
        db.close()

    assert row is not None
    category_id = row[0]

    response = client.post(
        f"/categories/{category_id}/edit",
        data={"name": "Updated Electronics"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT name FROM categories WHERE id = ?",
            (category_id,),
        ).fetchone()
        db.close()

    assert row[0] == "Updated Electronics"


def test_admin_can_delete_unused_category(client, app):
    sign_in(client)
    client.post("/categories/new", data={"name": "Unused Category"})

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        category_id = db.execute(
            "SELECT id FROM categories WHERE name = ?",
            ("Unused Category",),
        ).fetchone()[0]
        db.close()

    response = client.post(
        f"/categories/{category_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT id FROM categories WHERE id = ?",
            (category_id,),
        ).fetchone()
        db.close()

    assert row is None


def test_admin_can_create_edit_and_delete_supplier(client, app):
    sign_in(client)

    response = client.post(
        "/suppliers/new",
        data={"name": "Test Supplier Co"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT id FROM suppliers WHERE name = ?",
            ("Test Supplier Co",),
        ).fetchone()
        db.close()

    assert row is not None
    supplier_id = row[0]

    response = client.post(
        f"/suppliers/{supplier_id}/edit",
        data={"name": "Updated Supplier Co"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT name FROM suppliers WHERE id = ?",
            (supplier_id,),
        ).fetchone()
        db.close()

    assert row[0] == "Updated Supplier Co"

    response = client.post(
        f"/suppliers/{supplier_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT id FROM suppliers WHERE id = ?",
            (supplier_id,),
        ).fetchone()
        db.close()

    assert row is None

@pytest.mark.parametrize(
    ("url", "table"),
    [
        ("/categories/new", "categories"),
        ("/suppliers/new", "suppliers"),
    ],
)
def test_catalog_rejects_blank_names(client, app, url, table):
    sign_in(client)

    response = client.post(
        url,
        data={"name": "   "},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        count = db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE TRIM(name) = ''"
        ).fetchone()[0]
        db.close()

    assert count == 0


def test_duplicate_category_name_is_rejected(client, app):
    sign_in(client)
    client.post("/categories/new", data={"name": "Duplicate Category"})
    client.post("/categories/new", data={"name": "Duplicate Category"})

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        count = db.execute(
            "SELECT COUNT(*) FROM categories WHERE name = ?",
            ("Duplicate Category",),
        ).fetchone()[0]
        db.close()

    assert count == 1


def test_duplicate_supplier_name_is_rejected(client, app):
    sign_in(client)
    client.post("/suppliers/new", data={"name": "Duplicate Supplier"})
    client.post("/suppliers/new", data={"name": "Duplicate Supplier"})

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        count = db.execute(
            "SELECT COUNT(*) FROM suppliers WHERE name = ?",
            ("Duplicate Supplier",),
        ).fetchone()[0]
        db.close()

    assert count == 1


def test_cannot_delete_category_used_by_component(client, app):
    sign_in(client)

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        category_id = db.execute(
            "SELECT id FROM categories WHERE name = ?",
            ("Microcontrollers",),
        ).fetchone()[0]
        db.close()

    response = client.post(
        f"/categories/{category_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT id FROM categories WHERE id = ?",
            (category_id,),
        ).fetchone()
        db.close()

    assert row is not None


def test_cannot_delete_supplier_used_by_component(client, app):
    sign_in(client)

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        supplier_id = db.execute(
            "SELECT id FROM suppliers WHERE name = ?",
            ("Maker Supplies",),
        ).fetchone()[0]
        db.close()

    response = client.post(
        f"/suppliers/{supplier_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        from flask import current_app
        db = sqlite3.connect(current_app.config["DATABASE"])
        row = db.execute(
            "SELECT id FROM suppliers WHERE id = ?",
            (supplier_id,),
        ).fetchone()
        db.close()

    assert row is not None


def test_staff_cannot_manage_categories_or_suppliers(client, app):
    from werkzeug.security import generate_password_hash
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        db.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ("catalogstaff", "catalogstaff@example.com", generate_password_hash("SecureStaff123!"), "Staff"))
        db.commit()
        db.close()
    client.post("/login", data={"identity": "catalogstaff", "password": "SecureStaff123!"})
    assert client.get("/categories").status_code == 403
    assert client.get("/suppliers").status_code == 403
    assert client.post("/categories/new", data={"name": "Not Allowed"}).status_code == 403
    assert client.post("/suppliers/new", data={"name": "Not Allowed"}).status_code == 403


def test_renaming_catalogue_entry_updates_component_associations(client, app):
    sign_in(client)
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        category_id = db.execute("SELECT id FROM categories WHERE name = ?", ("Microcontrollers",)).fetchone()[0]
        supplier_id = db.execute("SELECT id FROM suppliers WHERE name = ?", ("Maker Supplies",)).fetchone()[0]
        db.close()
    assert client.post(f"/categories/{category_id}/edit", data={"name": "MCU boards"}, follow_redirects=True).status_code == 200
    assert client.post(f"/suppliers/{supplier_id}/edit", data={"name": "Maker Warehouse"}, follow_redirects=True).status_code == 200
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        category_count = db.execute("SELECT COUNT(*) FROM components WHERE category = ?", ("MCU boards",)).fetchone()[0]
        supplier_count = db.execute("SELECT COUNT(*) FROM components WHERE supplier = ?", ("Maker Warehouse",)).fetchone()[0]
        db.close()
    assert category_count > 0
    assert supplier_count > 0


def test_inventory_pagination_and_filters_preserve_query_state(client, app):
    sign_in(client)
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        db.executemany(
            """INSERT INTO components
               (sku, name, description, category, supplier, quantity, reorder_level, unit_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (f"PG-{index:03d}", f"Pagination Component {index:02d}", "Pagination acceptance test",
                 "Pagination Test", "Pagination Supplier", 20, 5, 1.0)
                for index in range(15)
            ],
        )
        db.commit()
        db.close()

    params = {
        "category": "Pagination Test",
        "supplier": "Pagination Supplier",
        "status": "In Stock",
    }
    first = client.get("/components", query_string={**params, "page": 1})
    first_page = first.get_data(as_text=True)
    assert first.status_code == 200
    assert "Page 1 of 2" in first_page
    assert "Pagination Component 00" in first_page
    assert "Pagination Component 14" not in first_page
    assert "page=2" in first_page

    second = client.get("/components", query_string={**params, "page": 2})
    second_page = second.get_data(as_text=True)
    assert second.status_code == 200
    assert "Page 2 of 2" in second_page
    assert "Pagination Component 14" in second_page
    assert "Pagination Component 00" not in second_page
