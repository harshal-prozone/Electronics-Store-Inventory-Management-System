import sqlite3

import pytest

from app import create_app, get_db
from inventory_service import adjust_stock


@pytest.fixture()
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "integration-test-secret",
        "DATABASE": str(tmp_path / "integration-inventory.sqlite"),
    })


@pytest.fixture()
def database(app):
    with app.app_context():
        yield get_db()


def create_component(db, sku="INTEGRATION-001", quantity=10):
    cursor = db.execute(
        """
        INSERT INTO components
            (sku, name, description, category, supplier,
             quantity, reorder_level, unit_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sku,
            "Integration Test Component",
            "Component created for integration testing",
            "Microcontrollers",
            "Test Supplier",
            quantity,
            3,
            250.00,
        ),
    )
    db.commit()
    return cursor.lastrowid


def test_component_creation_and_retrieval(database):
    component_id = create_component(database)

    component = database.execute(
        """
        SELECT id, sku, name, quantity, reorder_level, unit_price
        FROM components
        WHERE id = ?
        """,
        (component_id,),
    ).fetchone()

    assert component is not None
    assert component["sku"] == "INTEGRATION-001"
    assert component["name"] == "Integration Test Component"
    assert component["quantity"] == 10
    assert component["reorder_level"] == 3
    assert component["unit_price"] == 250.00


def test_complete_stock_in_and_stock_out_workflow(database):
    component_id = create_component(database, quantity=10)

    user_id = database.execute(
        "SELECT id FROM users WHERE username = 'admin'"
    ).fetchone()["id"]

    # Stock-in: 10 -> 15
    assert adjust_stock(
        database,
        component_id=component_id,
        user_id=user_id,
        adjustment="stock-in",
        quantity=5,
        note="Supplier delivery",
    ) == (10, 15)

    # Stock-out: 15 -> 12
    assert adjust_stock(
        database,
        component_id=component_id,
        user_id=user_id,
        adjustment="stock-out",
        quantity=3,
        note="Customer order",
    ) == (15, 12)

    component = database.execute(
        "SELECT quantity FROM components WHERE id = ?",
        (component_id,),
    ).fetchone()

    assert component["quantity"] == 12

    history = database.execute(
        """
        SELECT transaction_type, quantity,
               previous_quantity, new_quantity, note
        FROM inventory_transactions
        WHERE component_id = ?
        ORDER BY id
        """,
        (component_id,),
    ).fetchall()

    assert len(history) == 2

    assert tuple(history[0]) == (
        "stock-in", 5, 10, 15, "Supplier delivery"
    )
    assert tuple(history[1]) == (
        "stock-out", 3, 15, 12, "Customer order"
    )

    # Every transaction's resulting balance must match the next
    # transaction's starting balance.
    assert history[0]["new_quantity"] == history[1]["previous_quantity"]

    # The last recorded balance must equal the actual inventory balance.
    assert history[-1]["new_quantity"] == component["quantity"]

    audit_count = database.execute(
        """
        SELECT COUNT(*) FROM audit_log
        WHERE user_id = ? AND event_type = 'stock-adjustment'
        """,
        (user_id,),
    ).fetchone()[0]

    assert audit_count == 2


def test_insufficient_stock_does_not_change_inventory_or_history(database):
    component_id = create_component(database, quantity=3)

    user_id = database.execute(
        "SELECT id FROM users WHERE username = 'admin'"
    ).fetchone()["id"]

    with pytest.raises(ValueError, match="exceeds available stock"):
        adjust_stock(
            database,
            component_id=component_id,
            user_id=user_id,
            adjustment="stock-out",
            quantity=4,
        )

    quantity = database.execute(
        "SELECT quantity FROM components WHERE id = ?",
        (component_id,),
    ).fetchone()[0]

    transaction_count = database.execute(
        "SELECT COUNT(*) FROM inventory_transactions WHERE component_id = ?",
        (component_id,),
    ).fetchone()[0]

    audit_count = database.execute(
        """
        SELECT COUNT(*) FROM audit_log
        WHERE user_id = ? AND event_type = 'stock-adjustment'
        """,
        (user_id,),
    ).fetchone()[0]

    assert quantity == 3
    assert transaction_count == 0
    assert audit_count == 0


def test_missing_component_is_rejected_without_creating_history(database):
    user_id = database.execute(
        "SELECT id FROM users WHERE username = 'admin'"
    ).fetchone()["id"]

    with pytest.raises(LookupError, match="component not found"):
        adjust_stock(
            database,
            component_id=999999,
            user_id=user_id,
            adjustment="stock-in",
            quantity=5,
        )

    assert database.execute(
        "SELECT COUNT(*) FROM inventory_transactions"
    ).fetchone()[0] == 0


def test_database_failure_rolls_back_inventory_and_transaction(database):
    component_id = create_component(database, quantity=10)

    user_id = database.execute(
        "SELECT id FROM users WHERE username = 'admin'"
    ).fetchone()["id"]

    database.execute(
        """
        CREATE TRIGGER reject_stock_audit
        BEFORE INSERT ON audit_log
        WHEN NEW.event_type = 'stock-adjustment'
        BEGIN
            SELECT RAISE(ABORT, 'simulated audit failure');
        END
        """
    )
    database.commit()

    with pytest.raises(sqlite3.IntegrityError, match="simulated audit failure"):
        adjust_stock(
            database,
            component_id=component_id,
            user_id=user_id,
            adjustment="stock-in",
            quantity=5,
        )

    quantity = database.execute(
        "SELECT quantity FROM components WHERE id = ?",
        (component_id,),
    ).fetchone()[0]

    transaction_count = database.execute(
        "SELECT COUNT(*) FROM inventory_transactions WHERE component_id = ?",
        (component_id,),
    ).fetchone()[0]

    audit_count = database.execute(
        """
        SELECT COUNT(*) FROM audit_log
        WHERE user_id = ? AND event_type = 'stock-adjustment'
        """,
        (user_id,),
    ).fetchone()[0]

    assert quantity == 10
    assert transaction_count == 0
    assert audit_count == 0
