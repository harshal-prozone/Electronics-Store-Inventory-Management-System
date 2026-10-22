"""Flask web application for the Electronics Store Inventory Management System.

This is a coursework MVP focused on the inventory catalogue and Sprint 1 Issue #11:
availability classification and low-stock status updates. Broader backlog stories
(e.g. PDF reports, bulk imports, performance harnesses and full user administration)
are intentionally left for their own sprint branches.
"""

from __future__ import annotations

import csv
import io
import math
import os
import re
import sqlite3
from functools import wraps
from pathlib import Path
from typing import Any

import click
from flask import (
    Flask, abort, flash, g, jsonify, make_response, redirect, render_template,
    request, session, url_for,
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

from inventory_service import adjust_stock, availability_status

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "instance" / "inventory.db"
csrf = CSRFProtect()


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "local-development-key-change-before-deployment"),
        DATABASE=os.environ.get("DATABASE_PATH", str(DEFAULT_DB)),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=60 * 60,
        WTF_CSRF_TIME_LIMIT=None,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    csrf.init_app(app)
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    @app.before_request
    def load_logged_in_user() -> None:
        if request.endpoint == "health":
            g.user = None
            return
        user_id = session.get("user_id")
        g.user = get_db().execute(
            "SELECT id, username, email, role FROM users WHERE id = ?", (user_id,)
        ).fetchone() if user_id else None

    @app.context_processor
    def inject_helpers() -> dict[str, Any]:
        return {"availability_status": availability_status}

    @app.get("/")
    def index():
        if g.user is None:
            return redirect(url_for("login"))
        return redirect(url_for("components"))

    @app.route("/login", methods=("GET", "POST"))
    def login():
        if g.user is not None:
            return redirect(url_for("components"))
        if request.method == "POST":
            identity = request.form.get("identity", "").strip()
            password = request.form.get("password", "")
            user = get_db().execute(
                "SELECT * FROM users WHERE username = ? OR email = ?",
                (identity, identity),
            ).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Invalid username/email or password.", "error")
                write_audit(None, "login-failed", f"identity={identity[:120]}")
            else:
                session.clear()
                session.permanent = True
                session["user_id"] = user["id"]
                write_audit(user["id"], "login-success", f"username={user['username']}")
                flash(f"Welcome back, {user['username']}.", "success")
                return redirect(url_for("components"))
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        user_id = session.get("user_id")
        if user_id:
            write_audit(user_id, "logout", "user logged out")
        session.clear()
        flash("You have been signed out.", "success")
        return redirect(url_for("login"))

    @app.route("/admin/users", methods=("GET", "POST"))
    @login_required
    @admin_required
    def manage_users():
        db = get_db()

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "Staff").strip()

            if (
                not username
                or len(username) > 80
                or not email
                or len(email) > 254
                or "@" not in email
                or len(password) < 10
                or role not in ("Admin", "Staff")
            ):
                flash(
                    "Enter a valid username, email, role, and password "
                    "of at least 10 characters.",
                    "error",
                )
            else:
                try:
                    cursor = db.execute(
                        """INSERT INTO users
                           (username, email, password_hash, role)
                           VALUES (?, ?, ?, ?)""",
                        (
                            username,
                            email,
                            generate_password_hash(password),
                            role,
                        ),
                    )
                    db.commit()
                    write_audit(
                        g.user["id"],
                        "user-created",
                        f"user_id={cursor.lastrowid}; role={role}",
                    )
                    flash("User account created successfully.", "success")
                    return redirect(url_for("manage_users"))
                except sqlite3.IntegrityError:
                    db.rollback()
                    flash(
                        "That username or email is already registered.",
                        "error",
                    )

        users = db.execute(
            """SELECT id, username, email, role, created_at
               FROM users ORDER BY username COLLATE NOCASE"""
        ).fetchall()

        return render_template("user_management.html", users=users)
    @app.get("/components")
    @login_required
    def components():
        db = get_db()
        query = request.args.get("q", "").strip()[:100]
        status_filter = request.args.get("status", "").strip()
        category_filter = request.args.get("category", "").strip()[:80]
        supplier_filter = request.args.get("supplier", "").strip()[:80]
        page = max(request.args.get("page", 1, type=int) or 1, 1)
        per_page = 10
        where: list[str] = []
        params: list[Any] = []
        if query:
            where.append("(name LIKE ? OR sku LIKE ? OR description LIKE ?)")
            pattern = f"%{query}%"
            params.extend((pattern, pattern, pattern))
        if category_filter:
            where.append("category = ?")
            params.append(category_filter)
        if supplier_filter:
            where.append("supplier = ?")
            params.append(supplier_filter)
        if status_filter in ("Out of Stock", "Low Stock", "In Stock"):
            if status_filter == "Out of Stock":
                where.append("quantity = 0")
            elif status_filter == "Low Stock":
                where.append("quantity > 0 AND quantity <= reorder_level")
            else:
                where.append("quantity > reorder_level")
        where_sql = " WHERE " + " AND ".join(where) if where else ""
        total = db.execute("SELECT COUNT(*) FROM components" + where_sql, params).fetchone()[0]
        rows = db.execute(
            "SELECT * FROM components" + where_sql +
            " ORDER BY name COLLATE NOCASE LIMIT ? OFFSET ?",
            (*params, per_page, (page - 1) * per_page),
        ).fetchall()
        categories = [r[0] for r in db.execute(
            "SELECT DISTINCT category FROM components WHERE category <> '' ORDER BY category"
        ).fetchall()]
        suppliers = [r[0] for r in db.execute(
            "SELECT DISTINCT supplier FROM components WHERE supplier <> '' ORDER BY supplier"
        ).fetchall()]
        return render_template(
            "components.html", components=rows, q=query, status_filter=status_filter,
            category_filter=category_filter, supplier_filter=supplier_filter,
            categories=categories, suppliers=suppliers, page=page,
            pages=max((total + per_page - 1) // per_page, 1), total=total,
        )

    @app.route("/components/new", methods=("GET", "POST"))
    @login_required
    @admin_required
    def component_new():
        if request.method == "POST":
            values, error = validate_component_form(request.form)
            if error:
                flash(error, "error")
            else:
                try:
                    cursor = get_db().execute(
                        """INSERT INTO components
                           (sku, name, description, category, supplier, quantity, reorder_level, unit_price)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        values,
                    )
                    get_db().commit()
                    write_audit(g.user["id"], "component-created", f"component_id={cursor.lastrowid}; sku={values[0]}")
                    flash("Component added successfully.", "success")
                    return redirect(url_for("component_detail", component_id=cursor.lastrowid))
                except sqlite3.IntegrityError:
                    get_db().rollback()
                    flash("That SKU already exists. Use a unique SKU.", "error")
        return render_template("component_form.html", component=None, page_title="Add component")

    @app.route("/components/<int:component_id>/edit", methods=("GET", "POST"))
    @login_required
    @admin_required
    def component_edit(component_id: int):
        component = get_component_or_404(component_id)
        if request.method == "POST":
            values, error = validate_component_form(request.form)
            if error:
                flash(error, "error")
            else:
                try:
                    get_db().execute(
                        """UPDATE components SET sku=?, name=?, description=?, category=?, supplier=?,
                           quantity=?, reorder_level=?, unit_price=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                        (*values, component_id),
                    )
                    get_db().commit()
                    write_audit(g.user["id"], "component-updated", f"component_id={component_id}; sku={values[0]}")
                    flash("Component updated. Its availability label reflects the saved quantity and threshold.", "success")
                    return redirect(url_for("component_detail", component_id=component_id))
                except sqlite3.IntegrityError:
                    get_db().rollback()
                    flash("That SKU is already in use by another component.", "error")
        return render_template("component_form.html", component=component, page_title="Edit component")

    @app.get("/components/<int:component_id>")
    @login_required
    def component_detail(component_id: int):
        component = get_component_or_404(component_id)
        transactions = get_db().execute(
            """SELECT t.*, u.username FROM inventory_transactions t
               JOIN users u ON u.id = t.user_id
               WHERE t.component_id = ? ORDER BY t.id DESC LIMIT 20""",
            (component_id,),
        ).fetchall()
        return render_template("component_detail.html", component=component, transactions=transactions)

    @app.post("/components/<int:component_id>/stock")
    @login_required
    def component_stock(component_id: int):
        get_component_or_404(component_id)
        adjustment = request.form.get("adjustment", "")
        raw_quantity = request.form.get("quantity", "").strip()
        note = request.form.get("note", "").strip()[:250]
        if not raw_quantity.isdigit():
            flash("Enter a whole-number quantity greater than zero.", "error")
            return redirect(url_for("component_detail", component_id=component_id))
        quantity = int(raw_quantity)
        try:
            _, new_quantity = adjust_stock(
                get_db(), component_id=component_id, user_id=g.user["id"],
                adjustment=adjustment, quantity=quantity, note=note,
            )
            new_component = get_component_or_404(component_id)
            status = availability_status(new_quantity, int(new_component["reorder_level"]))
            flash(f"Stock updated. New quantity: {new_quantity}. Status: {status}.", "success")
        except (ValueError, LookupError, TypeError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("component_detail", component_id=component_id))

    @app.get("/health")
    def health():
        try:
            get_db().execute("SELECT 1").fetchone()
            return jsonify(status="ok", database="ok"), 200
        except sqlite3.Error:
            return jsonify(status="error", database="unavailable"), 503

    @app.get("/export/components.csv")
    @login_required
    def export_components_csv():
        rows = get_db().execute("SELECT * FROM components ORDER BY name COLLATE NOCASE").fetchall()
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["SKU", "Name", "Description", "Category", "Supplier", "Quantity", "Reorder Level", "Availability", "Unit Price"])
        for row in rows:
            writer.writerow([row["sku"], row["name"], row["description"], row["category"], row["supplier"], row["quantity"], row["reorder_level"], availability_status(row["quantity"], row["reorder_level"]), f"{row['unit_price']:.2f}"])
        response = make_response(buffer.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = "attachment; filename=inventory.csv"
        return response

    @app.cli.command("init-db")
    def init_db_command():
        """Create tables and seed a demo administrator and sample inventory."""
        init_db()
        click.echo("Database initialized. Demo login: admin / ChangeMe123! (change for real use).")

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin_command(username: str, email: str, password: str):
        """Create another administrator account."""
        if len(password) < 10:
            raise click.ClickException("Password must be at least 10 characters long.")
        try:
            get_db().execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'Admin')",
                (username.strip(), email.strip(), generate_password_hash(password)),
            )
            get_db().commit()
            click.echo(f"Administrator '{username}' created.")
        except sqlite3.IntegrityError as exc:
            raise click.ClickException("Username or email is already in use.") from exc

    return app


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database_path = Path(current_app_config_database())
        database_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database_path, timeout=10, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 10000")
    return g.db


def current_app_config_database() -> str:
    from flask import current_app
    return str(current_app.config["DATABASE"])


def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    from flask import current_app
    db = get_db()
    with open(ROOT / "schema.sql", encoding="utf-8") as schema_file:
        db.executescript(schema_file.read())
    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        admin_username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.local").strip() or "admin@example.local"
        admin_password = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")
        db.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'Admin')",
            (admin_username, admin_email, generate_password_hash(admin_password)),
        )
    component_count = db.execute("SELECT COUNT(*) FROM components").fetchone()[0]
    if component_count == 0:
        db.executemany(
            """INSERT INTO components
               (sku, name, description, category, supplier, quantity, reorder_level, unit_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                ("MCU-ARD-001", "Arduino Uno R3", "ATmega328P development board", "Microcontrollers", "Maker Supplies", 12, 5, 650.00),
                ("MCU-ESP-032", "ESP32 DevKit", "Wi-Fi and Bluetooth development board", "Microcontrollers", "Circuit Hub", 3, 5, 499.00),
                ("MCU-PICO-001", "Raspberry Pi Pico", "RP2040 microcontroller board", "Microcontrollers", "Circuit Hub", 0, 3, 399.00),
                ("SEN-DHT-022", "DHT22 Sensor", "Temperature and humidity sensor", "Sensors", "Maker Supplies", 8, 4, 280.00),
            ],
        )
    db.commit()


def write_audit(user_id: int | None, event_type: str, details: str) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO audit_log (user_id, event_type, details) VALUES (?, ?, ?)",
        (user_id, event_type, details[:500]),
    )
    db.commit()


def validate_component_form(form) -> tuple[tuple[Any, ...] | None, str | None]:
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
    return (sku, name, description, category, supplier, quantity, reorder_level, round(unit_price, 2)), None


def get_component_or_404(component_id: int):
    component = get_db().execute("SELECT * FROM components WHERE id = ?", (component_id,)).fetchone()
    if component is None:
        abort(404)
    return component


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)
    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        if g.user["role"] != "Admin":
            abort(403)
        return view(**kwargs)
    return wrapped_view


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
