import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from inventory_service import adjust_stock


def make_db(path, initial_quantity=5):
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL
        );

        CREATE TABLE components (
            id INTEGER PRIMARY KEY,
            quantity INTEGER NOT NULL CHECK (quantity >= 0),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_id INTEGER NOT NULL REFERENCES components(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            transaction_type TEXT NOT NULL
                CHECK (transaction_type IN ('stock-in', 'stock-out')),
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            previous_quantity INTEGER NOT NULL CHECK (previous_quantity >= 0),
            new_quantity INTEGER NOT NULL CHECK (new_quantity >= 0),
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type TEXT NOT NULL,
            details TEXT NOT NULL
        );

        INSERT INTO users (id, username) VALUES (1, 'tester');
    """)
    db.execute(
        "INSERT INTO components (id, quantity) VALUES (1, ?)",
        (initial_quantity,),
    )
    db.commit()
    db.close()


def connect_db(path, timeout=10):
    db = sqlite3.connect(path, timeout=timeout)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def test_stock_in_records_transaction_details(tmp_path):
    path = tmp_path / "stock-in.db"
    make_db(path, initial_quantity=0)
    db = connect_db(path)

    try:
        assert adjust_stock(
            db, component_id=1, user_id=1,
            adjustment="stock-in", quantity=3,
            note="  Supplier delivery  ",
        ) == (0, 3)

        row = db.execute(
            "SELECT * FROM inventory_transactions"
        ).fetchone()

        assert row["component_id"] == 1
        assert row["user_id"] == 1
        assert row["transaction_type"] == "stock-in"
        assert row["quantity"] == 3
        assert row["previous_quantity"] == 0
        assert row["new_quantity"] == 3
        assert row["note"] == "Supplier delivery"
        assert row["created_at"]
        assert db.execute(
            "SELECT quantity FROM components WHERE id=1"
        ).fetchone()[0] == 3
    finally:
        db.close()


def test_stock_out_records_transaction_details(tmp_path):
    path = tmp_path / "stock-out.db"
    make_db(path, initial_quantity=5)
    db = connect_db(path)

    try:
        assert adjust_stock(
            db, component_id=1, user_id=1,
            adjustment="stock-out", quantity=2,
            note="Customer order",
        ) == (5, 3)

        row = db.execute(
            "SELECT * FROM inventory_transactions"
        ).fetchone()

        assert row["component_id"] == 1
        assert row["user_id"] == 1
        assert row["transaction_type"] == "stock-out"
        assert row["quantity"] == 2
        assert row["previous_quantity"] == 5
        assert row["new_quantity"] == 3
        assert row["created_at"]
    finally:
        db.close()


def test_failed_stock_out_rolls_back_everything(tmp_path):
    path = tmp_path / "rollback.db"
    make_db(path, initial_quantity=3)
    db = connect_db(path)

    try:
        with pytest.raises(ValueError, match="exceeds available stock"):
            adjust_stock(
                db, component_id=1, user_id=1,
                adjustment="stock-out", quantity=4,
            )

        assert db.execute(
            "SELECT quantity FROM components WHERE id=1"
        ).fetchone()[0] == 3
        assert db.execute(
            "SELECT COUNT(*) FROM inventory_transactions"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM audit_log"
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_concurrent_stock_out_cannot_overspend(tmp_path):
    path = tmp_path / "concurrent.db"
    make_db(path, initial_quantity=5)
    barrier = threading.Barrier(2)

    def issue_four_units():
        db = connect_db(path)
        try:
            barrier.wait(timeout=5)
            adjust_stock(
                db, component_id=1, user_id=1,
                adjustment="stock-out", quantity=4,
            )
            return "success"
        except ValueError as exc:
            if "exceeds available stock" not in str(exc):
                raise
            return "rejected"
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(issue_four_units),
            pool.submit(issue_four_units),
        ]
        outcomes = [future.result(timeout=15) for future in futures]

    assert sorted(outcomes) == ["rejected", "success"]

    db = connect_db(path)
    try:
        assert db.execute(
            "SELECT quantity FROM components WHERE id=1"
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM inventory_transactions"
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM audit_log"
        ).fetchone()[0] == 1
    finally:
        db.close()
