import sqlite3

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
