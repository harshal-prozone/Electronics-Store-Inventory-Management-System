"""Flask web application for the Electronics Store Inventory Management System.

Sprint 1 functionality includes authentication and role controls, component CRUD,
recorded stock movements, availability classification, and filtered availability
reports with CSV/PDF exports. Performance claims require a recorded load-test run.
"""

from __future__ import annotations

import csv
import io
import math
import os
import re
import secrets
import sqlite3
from datetime import date
from functools import wraps
from pathlib import Path
from typing import Any

import click
from flask import (
    Flask, abort, flash, g, jsonify, make_response, redirect, render_template,
    request, session, url_for,
)
from flask_wtf.csrf import CSRFProtect
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape
from werkzeug.security import check_password_hash, generate_password_hash

from inventory_service import adjust_stock, availability_status

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "instance" / "inventory.db"
csrf = CSRFProtect()


def safe_csv_cell(value: Any) -> Any:
    """Keep untrusted text from being evaluated as a spreadsheet formula."""
    if not isinstance(value, str):
        return value
    significant = value.lstrip(" \t\r\n")
    if value.startswith(("\t", "\r")) or significant.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    environment = os.environ.get("APP_ENV", "development").strip().lower()
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        if environment == "production":
            raise RuntimeError("SECRET_KEY must be set when APP_ENV=production.")
        # A random development key avoids a predictable, forgeable session key.
        # Configure a persistent SECRET_KEY when sessions must survive restarts.
        secret_key = secrets.token_hex(32)

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=secret_key,
        APP_ENV=environment,
        DATABASE=os.environ.get("DATABASE_PATH", str(DEFAULT_DB)),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "1" if environment == "production" else "0") == "1",
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
        where: list[str] = ["deleted_at IS NULL"]
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
            "SELECT DISTINCT category FROM components WHERE deleted_at IS NULL AND category <> '' ORDER BY category"
        ).fetchall()]
        suppliers = [r[0] for r in db.execute(
            "SELECT DISTINCT supplier FROM components WHERE deleted_at IS NULL AND supplier <> '' ORDER BY supplier"
        ).fetchall()]
        return render_template(
            "components.html", components=rows, q=query, status_filter=status_filter,
            category_filter=category_filter, supplier_filter=supplier_filter,
            categories=categories, suppliers=suppliers, page=page,
            pages=max((total + per_page - 1) // per_page, 1), total=total,
        )
    
    def get_catalog_options():
        db = get_db()
        categories = db.execute(
            "SELECT id, name FROM categories ORDER BY name COLLATE NOCASE"
        ).fetchall()
        suppliers = db.execute(
            "SELECT id, name FROM suppliers ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return categories, suppliers
    
    def validate_catalog_selection(values):
        """Ensure component category and supplier exist in the catalogues."""
        db = get_db()
        category = db.execute(
            "SELECT 1 FROM categories WHERE name = ? COLLATE NOCASE",
            (values[3],),
        ).fetchone()
        supplier = db.execute(
            "SELECT 1 FROM suppliers WHERE name = ? COLLATE NOCASE",
            (values[4],),
        ).fetchone()

        if not category:
            return "Select a valid category from the catalogue."
        if not supplier:
            return "Select a valid supplier from the catalogue."
        return None

    @app.route("/components/new", methods=("GET", "POST"))
    @login_required
    @admin_required
    def component_new():
        if request.method == "POST":
            values, error = validate_component_form(request.form)
            if not error:
                error = validate_catalog_selection(values)
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
        categories, suppliers = get_catalog_options()
        return render_template("component_form.html", component=None, page_title="Add component",
                               categories=categories, suppliers=suppliers)

    @app.route("/components/<int:component_id>/edit", methods=("GET", "POST"))
    @login_required
    @admin_required
    def component_edit(component_id: int):
        component = get_component_or_404(component_id)
        if request.method == "POST":
            form_data = request.form.copy()
            form_data["quantity"] = str(component["quantity"])
            values, error = validate_component_form(form_data)
            if not error:
                error = validate_catalog_selection(values)
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
        categories, suppliers = get_catalog_options()
        return render_template("component_form.html", component=component, page_title="Edit component",
                               categories=categories, suppliers=suppliers)

    
    @app.get("/components/<int:component_id>")
    @login_required
    def component_detail(component_id: int):
        component = get_component_or_404(component_id)
        start_date = request.args.get("start_date", "").strip()
        end_date = request.args.get("end_date", "").strip()
        transaction_type = request.args.get("transaction_type", "").strip()
        error = None
        try:
            for value in (start_date, end_date):
                if value:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        raise ValueError
                    date.fromisoformat(value)
            if start_date and end_date and start_date > end_date:
                error = "Start date must be on or before end date."
        except ValueError:
            error = "Enter valid dates in YYYY-MM-DD format."
        if transaction_type not in ("", "stock-in", "stock-out", "adjustment"):
            error = "Select a valid transaction type."
        conditions = ["t.component_id = ?"]
        params = [component_id]
        if not error:
            if start_date:
                conditions.append("t.created_at >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("t.created_at <= ?")
                params.append(end_date + " 23:59:59.999999")
            if transaction_type:
                conditions.append("t.transaction_type = ?")
                params.append(transaction_type)
        else:
            flash(error, "error")
            conditions.append("0 = 1")
        where = " AND ".join(conditions)
        db = get_db()
        total = db.execute(
            "SELECT COUNT(*) FROM inventory_transactions t WHERE " + where, params,
        ).fetchone()[0]
        pages = max(1, (total + 19) // 20)
        page = min(max(1, request.args.get("page", 1, type=int) or 1), pages)
        transactions = db.execute(
            """SELECT t.*, u.username FROM inventory_transactions t
               LEFT JOIN users u ON u.id = t.user_id WHERE """ + where +
            " ORDER BY t.created_at DESC, t.id DESC LIMIT 20 OFFSET ?",
            (*params, (page - 1) * 20),
        ).fetchall()
        return render_template(
            "component_detail.html",
            component=component,
            transactions=transactions,
            start_date=start_date, end_date=end_date, transaction_type=transaction_type,
            page=page, pages=pages, total=total,
        ), 400 if error else 200

    @app.post("/components/<int:component_id>/threshold")
    @login_required
    @admin_required
    def component_threshold(component_id: int):
        get_component_or_404(component_id)
        raw_threshold = request.form.get("reorder_level", "").strip()
        # SQLite INTEGER values are signed 64-bit; reject oversized inputs too.
        if (not re.fullmatch(r"[0-9]{1,19}", raw_threshold)
                or int(raw_threshold) > 9223372036854775807):
            flash("Minimum stock threshold must be a non-negative whole number within the supported range.", "error")
            return redirect(url_for("component_detail", component_id=component_id))

        threshold = int(raw_threshold)
        db = get_db()
        with db:
            previous = db.execute(
                """UPDATE components SET reorder_level = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND deleted_at IS NULL RETURNING quantity""",
                (threshold, component_id),
            ).fetchone()
            if previous is None:
                abort(404)
            db.execute(
                "INSERT INTO audit_log (user_id, event_type, details) VALUES (?, ?, ?)",
                (g.user["id"], "threshold-updated", f"component_id={component_id}; reorder_level={threshold}"),
            )
        status = availability_status(previous["quantity"], threshold)
        flash(f"Minimum stock threshold updated to {threshold}. Status: {status}.", "success")
        return redirect(url_for("component_detail", component_id=component_id))

    @app.post("/components/<int:component_id>/delete")
    @login_required
    @admin_required
    def component_delete(component_id: int):
        db = get_db()
        component = get_component_or_404(component_id)

        db.execute(
            """UPDATE components
               SET deleted_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND deleted_at IS NULL""",
            (component_id,),
        )
        db.commit()

        write_audit(
            g.user["id"],
            "component-deleted",
            f"component_id={component_id}; sku={component['sku']}",
        )

        flash("Component moved out of active inventory.", "success")
        return redirect(url_for("components"))

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
    
    @app.get("/categories")
    @login_required
    @admin_required
    def categories():
        rows = get_db().execute(
            "SELECT * FROM categories ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return render_template("categories.html", categories=rows)

    @app.route("/categories/new", methods=("GET", "POST"))
    @login_required
    @admin_required
    def category_new():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name or len(name) > 80:
                flash("Category name is required and must be 80 characters or fewer.", "error")
            else:
                try:
                    db = get_db()
                    cursor = db.execute(
                        "INSERT INTO categories (name) VALUES (?)", (name,)
                    )
                    db.commit()
                    write_audit(g.user["id"], "category-created", f"category_id={cursor.lastrowid}; name={name}")
                    flash("Category created successfully.", "success")
                    return redirect(url_for("categories"))
                except sqlite3.IntegrityError:
                    get_db().rollback()
                    flash("A category with that name already exists.", "error")
        return render_template("catalog_form.html", page_title="Add category", item_type="Category")

    @app.route("/categories/<int:category_id>/edit", methods=("GET", "POST"))
    @login_required
    @admin_required
    def category_edit(category_id: int):
        db = get_db()
        category = db.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if category is None:
            abort(404)

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name or len(name) > 80:
                flash("Category name is required and must be 80 characters or fewer.", "error")
            else:
                old_name = category["name"]
                try:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute(
                        "UPDATE categories SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (name, category_id),
                    )
                    db.execute(
                        "UPDATE components SET category = ? WHERE category = ?",
                        (name, old_name),
                    )
                    db.commit()
                    write_audit(g.user["id"], "category-updated", f"category_id={category_id}; name={name}")
                    flash("Category updated successfully.", "success")
                    return redirect(url_for("categories"))
                except sqlite3.IntegrityError:
                    db.rollback()
                    flash("A category with that name already exists.", "error")
        return render_template("catalog_form.html", page_title="Edit category", item_type="Category", item=category)

    @app.post("/categories/<int:category_id>/delete")
    @login_required
    @admin_required
    def category_delete(category_id: int):
        db = get_db()
        category = db.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if category is None:
            abort(404)

        used = db.execute(
            "SELECT 1 FROM components WHERE category = ? AND deleted_at IS NULL LIMIT 1",
            (category["name"],),
        ).fetchone()
        if used:
            flash("Cannot delete a category assigned to an active component.", "error")
        else:
            db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            db.commit()
            write_audit(g.user["id"], "category-deleted", f"category_id={category_id}; name={category['name']}")
            flash("Category deleted successfully.", "success")
        return redirect(url_for("categories"))

    @app.get("/suppliers")
    @login_required
    @admin_required
    def suppliers():
        rows = get_db().execute(
            "SELECT * FROM suppliers ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return render_template("suppliers.html", suppliers=rows)

    @app.route("/suppliers/new", methods=("GET", "POST"))
    @login_required
    @admin_required
    def supplier_new():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name or len(name) > 120:
                flash("Supplier name is required and must be 120 characters or fewer.", "error")
            else:
                try:
                    db = get_db()
                    cursor = db.execute(
                        "INSERT INTO suppliers (name) VALUES (?)", (name,)
                    )
                    db.commit()
                    write_audit(g.user["id"], "supplier-created", f"supplier_id={cursor.lastrowid}; name={name}")
                    flash("Supplier created successfully.", "success")
                    return redirect(url_for("suppliers"))
                except sqlite3.IntegrityError:
                    get_db().rollback()
                    flash("A supplier with that name already exists.", "error")
        return render_template("catalog_form.html", page_title="Add supplier", item_type="Supplier")

    @app.route("/suppliers/<int:supplier_id>/edit", methods=("GET", "POST"))
    @login_required
    @admin_required
    def supplier_edit(supplier_id: int):
        db = get_db()
        supplier = db.execute(
            "SELECT * FROM suppliers WHERE id = ?", (supplier_id,)
        ).fetchone()
        if supplier is None:
            abort(404)

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name or len(name) > 120:
                flash("Supplier name is required and must be 120 characters or fewer.", "error")
            else:
                old_name = supplier["name"]
                try:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute(
                        "UPDATE suppliers SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (name, supplier_id),
                    )
                    db.execute(
                        "UPDATE components SET supplier = ? WHERE supplier = ?",
                        (name, old_name),
                    )
                    db.commit()
                    write_audit(g.user["id"], "supplier-updated", f"supplier_id={supplier_id}; name={name}")
                    flash("Supplier updated successfully.", "success")
                    return redirect(url_for("suppliers"))
                except sqlite3.IntegrityError:
                    db.rollback()
                    flash("A supplier with that name already exists.", "error")
        return render_template("catalog_form.html", page_title="Edit supplier", item_type="Supplier", item=supplier)

    @app.post("/suppliers/<int:supplier_id>/delete")
    @login_required
    @admin_required
    def supplier_delete(supplier_id: int):
        db = get_db()
        supplier = db.execute(
            "SELECT * FROM suppliers WHERE id = ?", (supplier_id,)
        ).fetchone()
        if supplier is None:
            abort(404)

        used = db.execute(
            "SELECT 1 FROM components WHERE supplier = ? AND deleted_at IS NULL LIMIT 1",
            (supplier["name"],),
        ).fetchone()
        if used:
            flash("Cannot delete a supplier assigned to an active component.", "error")
        else:
            db.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
            db.commit()
            write_audit(g.user["id"], "supplier-deleted", f"supplier_id={supplier_id}; name={supplier['name']}")
            flash("Supplier deleted successfully.", "success")
        return redirect(url_for("suppliers"))


    @app.get("/health")
    def health():
        try:
            get_db().execute("SELECT 1").fetchone()
            return jsonify(status="ok", database="ok"), 200
        except sqlite3.Error:
            return jsonify(status="error", database="unavailable"), 503

    @app.get("/reports/availability")
    @login_required
    @admin_required
    def availability_report():
        category_filter, supplier_filter, status_filter = get_availability_report_filters()
        db = get_db()
        rows = get_availability_report_rows(
            db, category_filter, supplier_filter, status_filter
        )
        categories = [
            row[0] for row in db.execute(
                """SELECT DISTINCT category FROM components
                   WHERE deleted_at IS NULL AND category <> ''
                   ORDER BY category COLLATE NOCASE"""
            ).fetchall()
        ]
        suppliers = [
            row[0] for row in db.execute(
                """SELECT DISTINCT supplier FROM components
                   WHERE deleted_at IS NULL AND supplier <> ''
                   ORDER BY supplier COLLATE NOCASE"""
            ).fetchall()
        ]
        return render_template(
            "availability_report.html",
            components=rows,
            categories=categories,
            suppliers=suppliers,
            category_filter=category_filter,
            supplier_filter=supplier_filter,
            status_filter=status_filter,
            report_data=availability_report_data(rows),
        )

    @app.get("/reports/availability.csv")
    @login_required
    @admin_required
    def export_availability_report_csv():
        category, supplier, status = get_availability_report_filters()
        rows = get_availability_report_rows(get_db(), category, supplier, status)
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow([
            "SKU", "Component", "Category", "Supplier", "Quantity",
            "Reorder Level", "Availability", "Unit Price (INR)",
        ])
        writer.writerows([[safe_csv_cell(value) for value in record] for record in availability_report_data(rows)])
        response = make_response(buffer.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = (
            'attachment; filename="availability-report.csv"'
        )
        return response

    @app.get("/reports/availability.pdf")
    @login_required
    @admin_required
    def export_availability_report_pdf():
        category, supplier, status = get_availability_report_filters()
        rows = get_availability_report_rows(get_db(), category, supplier, status)
        records = availability_report_data(rows)

        buffer = io.BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            rightMargin=0.45 * inch,
            leftMargin=0.45 * inch,
            topMargin=0.45 * inch,
            bottomMargin=0.45 * inch,
            title="Inventory Availability Report",
        )
        styles = getSampleStyleSheet()
        filter_text = (
            f"Category: {category or 'All'} | "
            f"Supplier: {supplier or 'All'} | "
            f"Status: {status or 'All'}"
        )
        story = [
            Paragraph("Inventory Availability Report", styles["Title"]),
            Paragraph(escape(filter_text), styles["Normal"]),
            Spacer(1, 0.18 * inch),
        ]
        headers = [
            "SKU", "Component", "Category", "Supplier", "Quantity",
            "Reorder Level", "Status", "Unit Price (INR)",
        ]
        table_data = [
            [Paragraph(escape(value), styles["BodyText"]) for value in headers]
        ]
        for record in records:
            table_data.append([
                Paragraph(escape(str(value)), styles["BodyText"])
                for value in record
            ])

        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[
                1.15 * inch, 1.55 * inch, 1.20 * inch, 1.45 * inch,
                0.70 * inch, 0.95 * inch, 0.95 * inch, 1.20 * inch,
            ],
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18324A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D7E0E8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F3F6F9")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
        document.build(story)

        response = make_response(buffer.getvalue())
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = (
            'attachment; filename="availability-report.pdf"'
        )
        return response

    @app.get("/export/components.csv")
    @login_required
    def export_components_csv():
        rows = get_db().execute("SELECT * FROM components WHERE deleted_at IS NULL ORDER BY name COLLATE NOCASE").fetchall()
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["SKU", "Name", "Description", "Category", "Supplier", "Quantity", "Reorder Level", "Availability", "Unit Price"])
        for row in rows:
            writer.writerow([safe_csv_cell(value) for value in [
                row["sku"], row["name"], row["description"], row["category"],
                row["supplier"], row["quantity"], row["reorder_level"],
                availability_status(row["quantity"], row["reorder_level"]),
                f"{row['unit_price']:.2f}",
            ]])
        response = make_response(buffer.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = "attachment; filename=inventory.csv"
        return response

    @app.cli.command("init-db")
    def init_db_command():
        """Create tables and seed a demo administrator and sample inventory."""
        init_db()
        click.echo("Database initialized. If no administrator exists, run: flask --app app create-admin")

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

    # SQLite CHECK constraints require rebuilding the table to add a type.
    transaction_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'inventory_transactions'"
    ).fetchone()[0]
    if "'adjustment'" not in transaction_sql:
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(transaction_sql.replace(
                "inventory_transactions", "inventory_transactions_new", 1
            ).replace("'stock-in', 'stock-out'", "'stock-in', 'stock-out', 'adjustment'"))
            db.execute("INSERT INTO inventory_transactions_new SELECT * FROM inventory_transactions")
            db.execute("DROP TABLE inventory_transactions")
            db.execute("ALTER TABLE inventory_transactions_new RENAME TO inventory_transactions")
            db.execute("CREATE INDEX idx_transactions_component_date "
                       "ON inventory_transactions(component_id, created_at DESC)")
    
    


    # Safely migrate databases created before soft deletion was introduced.
    columns = {
        row["name"]
        for row in db.execute("PRAGMA table_info(components)").fetchall()
    }
    if "deleted_at" not in columns:
        db.execute("ALTER TABLE components ADD COLUMN deleted_at TEXT DEFAULT NULL")

    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        # Tests use a deterministic test-only account; normal installs never get
        # a known default password. Without ADMIN_PASSWORD, use create-admin CLI.
        if current_app.config.get("TESTING"):
            admin_password = "ChangeMe123!"
        else:
            admin_password = os.environ.get("ADMIN_PASSWORD", "")

        if admin_password:
            if len(admin_password) < 10:
                raise RuntimeError("ADMIN_PASSWORD must be at least 10 characters long.")
            admin_username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
            admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.local").strip() or "admin@example.local"
            db.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'Admin')",
                (admin_username, admin_email, generate_password_hash(admin_password)),
            )
        elif not current_app.config.get("TESTING"):
            current_app.logger.warning(
                "No administrator was seeded. Run 'flask --app app create-admin' to create one."
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
        # Migrate existing component categories into the categories table.
    db.execute(
        """INSERT OR IGNORE INTO categories (name)
           SELECT DISTINCT TRIM(category)
           FROM components
           WHERE TRIM(category) <> ''"""
    )

    # Migrate existing component suppliers into the suppliers table.
    db.execute(
        """INSERT OR IGNORE INTO suppliers (name)
           SELECT DISTINCT TRIM(supplier)
           FROM components
           WHERE TRIM(supplier) <> ''"""
    )

    db.commit()

    # Preserve existing values while seeding administrator-managed catalogues.
    db.execute(
        """INSERT OR IGNORE INTO categories (name)
           SELECT DISTINCT TRIM(category) FROM components
           WHERE deleted_at IS NULL AND TRIM(category) <> ''"""
    )
    db.execute(
        """INSERT OR IGNORE INTO suppliers (name)
           SELECT DISTINCT TRIM(supplier) FROM components
           WHERE deleted_at IS NULL AND TRIM(supplier) <> ''"""
    )
    db.commit()

def get_availability_report_filters():
    """Read and normalize report filters from the query string."""
    category = request.args.get("category", "").strip()[:80]
    supplier = request.args.get("supplier", "").strip()[:120]
    status = request.args.get("status", "").strip()
    valid_statuses = {"", "In Stock", "Low Stock", "Out of Stock"}
    if status not in valid_statuses:
        status = ""
    return category, supplier, status


def get_availability_report_rows(db, category="", supplier="", status=""):
    """Return active inventory rows matching the selected report filters."""
    conditions = ["deleted_at IS NULL"]
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)
    if supplier:
        conditions.append("supplier = ?")
        params.append(supplier)

    if status == "Out of Stock":
        conditions.append("quantity = 0")
    elif status == "Low Stock":
        conditions.append("quantity > 0 AND quantity <= reorder_level")
    elif status == "In Stock":
        conditions.append("quantity > reorder_level")

    sql = """
        SELECT sku, name, category, supplier, quantity, reorder_level, unit_price
        FROM components
        WHERE """ + " AND ".join(conditions) + """
        ORDER BY name COLLATE NOCASE
    """
    return db.execute(sql, params).fetchall()


def availability_report_data(rows):
    """Format report data consistently for CSV and PDF exports."""
    return [
        [
            row["sku"],
            row["name"],
            row["category"] or "",
            row["supplier"] or "",
            row["quantity"],
            row["reorder_level"],
            availability_status(int(row["quantity"]), int(row["reorder_level"])),
            f"{row['unit_price']:.2f}",
        ]
        for row in rows
    ]


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
    component = get_db().execute(
        "SELECT * FROM components WHERE id = ? AND deleted_at IS NULL",
        (component_id,)
    ).fetchone()
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
