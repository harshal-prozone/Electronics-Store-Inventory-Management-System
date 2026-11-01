import pytest

from inventory_service import availability_status


@pytest.mark.parametrize(
    ("quantity", "reorder_level", "expected"),
    [
        (0, 5, "Out of Stock"),
        (0, 0, "Out of Stock"),  # zero always takes priority over threshold
        (1, 5, "Low Stock"),
        (5, 5, "Low Stock"),  # exact threshold boundary
        (6, 5, "In Stock"),
        (1, 0, "In Stock"),  # positive quantity above zero threshold
        (100, 5, "In Stock"),
    ],
)
def test_availability_boundaries(quantity, reorder_level, expected):
    assert availability_status(quantity, reorder_level) == expected


@pytest.mark.parametrize(
    ("quantity", "reorder_level"),
    [(-1, 5), (1, -1)],
)
def test_negative_inventory_values_are_rejected(quantity, reorder_level):
    with pytest.raises(ValueError):
        availability_status(quantity, reorder_level)


@pytest.mark.parametrize(("quantity", "threshold"), [("2", 3), (True, 3), (3, 2.0)])
def test_non_integer_values_are_rejected(quantity, threshold):
    with pytest.raises(TypeError):
        availability_status(quantity, threshold)


def _transaction_test_db():
    import sqlite3

    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL);
        CREATE TABLE components (
            id INTEGER PRIMARY KEY, quantity INTEGER NOT NULL CHECK (quantity >= 0),
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE inventory_transactions (
            id INTEGER PRIMARY KEY, component_id INTEGER NOT NULL REFERENCES components(id),
            user_id INTEGER NOT NULL REFERENCES users(id), transaction_type TEXT NOT NULL,
            quantity INTEGER NOT NULL, previous_quantity INTEGER NOT NULL,
            new_quantity INTEGER NOT NULL, note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY, user_id INTEGER, event_type TEXT, details TEXT
        );
        INSERT INTO users (id, username) VALUES (1, 'tester');
        INSERT INTO components (id, quantity) VALUES (1, 5);
        """
    )
    db.commit()
    return db


def test_stock_adjustment_updates_quantity_and_logs_transaction():
    from inventory_service import adjust_stock

    db = _transaction_test_db()
    previous, new = adjust_stock(
        db, component_id=1, user_id=1, adjustment="stock-out", quantity=2, note="test"
    )
    assert (previous, new) == (5, 3)
    assert db.execute("SELECT quantity FROM components WHERE id=1").fetchone()[0] == 3
    row = db.execute("SELECT * FROM inventory_transactions").fetchone()
    assert row["previous_quantity"] == 5
    assert row["new_quantity"] == 3
    assert row["quantity"] == 2
    assert db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1
    db.close()


def test_failed_stock_out_rolls_back_without_log_entry():
    from inventory_service import adjust_stock

    db = _transaction_test_db()
    with pytest.raises(ValueError, match="exceeds available stock"):
        adjust_stock(db, component_id=1, user_id=1, adjustment="stock-out", quantity=6)
    assert db.execute("SELECT quantity FROM components WHERE id=1").fetchone()[0] == 5
    assert db.execute("SELECT COUNT(*) FROM inventory_transactions").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0
    db.close()


def test_stock_in_increments_quantity():
    from inventory_service import adjust_stock

    db = _transaction_test_db()
    assert adjust_stock(db, component_id=1, user_id=1, adjustment="stock-in", quantity=4) == (5, 9)
    assert db.execute("SELECT quantity FROM components WHERE id=1").fetchone()[0] == 9
    db.close()


def _valid_component_form(**overrides):
    form = {
        "sku": " arduino-uno ",
        "name": " Arduino Uno ",
        "description": " Microcontroller board ",
        "category": "Electronics",
        "supplier": "Arduino",
        "quantity": "10",
        "reorder_level": "5",
        "unit_price": "250.567",
    }
    form.update(overrides)
    return form


def test_component_form_normalizes_and_rounds_values():
    from inventory_service import validate_component_form

    values, error = validate_component_form(_valid_component_form())

    assert error is None
    assert values == (
        "ARDUINO-UNO",
        "Arduino Uno",
        "Microcontroller board",
        "Electronics",
        "Arduino",
        10,
        5,
        250.57,
    )


@pytest.mark.parametrize(
    "sku",
    ["", "INVALID SKU", "SKU@123", "-INVALID"],
)
def test_component_form_rejects_invalid_skus(sku):
    from inventory_service import validate_component_form

    values, error = validate_component_form(_valid_component_form(sku=sku))

    assert values is None
    assert error is not None


@pytest.mark.parametrize(
    "name",
    ["", " "],
)
def test_component_form_rejects_blank_names(name):
    from inventory_service import validate_component_form

    values, error = validate_component_form(_valid_component_form(name=name))

    assert values is None
    assert error is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"quantity": "abc"},
        {"reorder_level": "1.5"},
        {"unit_price": "not-a-number"},
        {"quantity": "-1"},
        {"reorder_level": "-1"},
        {"unit_price": "-10"},
        {"unit_price": "nan"},
        {"unit_price": "inf"},
    ],
)
def test_component_form_rejects_invalid_numeric_values(overrides):
    from inventory_service import validate_component_form

    values, error = validate_component_form(_valid_component_form(**overrides))

    assert values is None
    assert error is not None


def test_stock_adjustment_rejects_invalid_operation():
    from inventory_service import adjust_stock

    db = _transaction_test_db()

    with pytest.raises(ValueError, match="adjustment must be"):
        adjust_stock(
            db,
            component_id=1,
            user_id=1,
            adjustment="invalid",
            quantity=1,
        )

    db.close()


@pytest.mark.parametrize("quantity", [0, -1])
def test_stock_adjustment_rejects_non_positive_quantity(quantity):
    from inventory_service import adjust_stock

    db = _transaction_test_db()

    with pytest.raises(ValueError, match="greater than zero"):
        adjust_stock(
            db,
            component_id=1,
            user_id=1,
            adjustment="stock-out",
            quantity=quantity,
        )

    db.close()


def test_stock_adjustment_rejects_boolean_quantity():
    from inventory_service import adjust_stock

    db = _transaction_test_db()

    with pytest.raises(TypeError, match="must be an integer"):
        adjust_stock(
            db,
            component_id=1,
            user_id=1,
            adjustment="stock-in",
            quantity=True,
        )

    db.close()


def test_stock_adjustment_rejects_missing_component():
    from inventory_service import adjust_stock

    db = _transaction_test_db()

    with pytest.raises(LookupError, match="component not found"):
        adjust_stock(
            db,
            component_id=999,
            user_id=1,
            adjustment="stock-in",
            quantity=1,
        )

    assert db.execute(
        "SELECT COUNT(*) FROM inventory_transactions"
    ).fetchone()[0] == 0

    db.close()
