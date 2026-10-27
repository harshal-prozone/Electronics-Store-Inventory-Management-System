#!/usr/bin/env python3
"""Cross-browser Sprint 1 smoke test, invoked by GitHub Actions.

Required environment: ESIMS_BROWSER=chrome|edge|firefox. It runs an isolated app
against a temporary SQLite DB and exercises core screen flows, so it never mutates a
normal developer database. This is automated compatibility evidence, not a substitute
for a real representative-user interview/usability session.
"""
from __future__ import annotations

import os
import tempfile
import threading
import sys
from pathlib import Path

TEMP_DIR = tempfile.TemporaryDirectory(prefix="esims-browser-acceptance-")
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "browser-acceptance-only-not-for-production"
os.environ["DATABASE_PATH"] = str(Path(TEMP_DIR.name) / "browser.sqlite")
os.environ.pop("ADMIN_PASSWORD", None)
os.environ.pop("ADMIN_USERNAME", None)
os.environ.pop("ADMIN_EMAIL", None)

# Allow this script to import app.py from the repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from playwright.sync_api import expect, sync_playwright  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402
from app import create_app, get_db  # noqa: E402

ADMIN_PASSWORD = "ChangeMe123!"  # Deterministic test-only account from TESTING config.
STAFF_PASSWORD = "BrowserStaff123!"


def seed_browser_records(flask_app) -> None:
    with flask_app.app_context():
        db = get_db()
        db.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", ("Browser Matrix",))
        db.execute("INSERT OR IGNORE INTO suppliers (name) VALUES (?)", ("Browser Matrix Supplier",))
        db.executemany(
            """INSERT OR IGNORE INTO components
               (sku, name, description, category, supplier, quantity, reorder_level, unit_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (f"BROWSE-PG-{i:03d}", f"Browser Pagination Component {i:02d}",
                 "Generated browser acceptance row", "Browser Matrix", "Browser Matrix Supplier",
                 20, 5, 1.0)
                for i in range(15)
            ],
        )
        staff = db.execute("SELECT id FROM users WHERE username = ?", ("browserstaff",)).fetchone()
        if staff is None:
            db.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'Staff')",
                ("browserstaff", "browserstaff@example.invalid", generate_password_hash(STAFF_PASSWORD)),
            )
        db.commit()


def login(page, identity: str, password: str, base_url: str) -> None:
    page.goto(f"{base_url}/login")
    page.locator("#identity").fill(identity)
    page.locator("#password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url("**/components")


def run() -> None:
    browser_name = os.environ.get("ESIMS_BROWSER", "chrome").lower()
    if browser_name not in {"chrome", "edge", "firefox"}:
        raise SystemExit("ESIMS_BROWSER must be chrome, edge, or firefox")

    flask_app = create_app({
        "TESTING": True,
        "DATABASE": os.environ["DATABASE_PATH"],
        "SECRET_KEY": os.environ["SECRET_KEY"],
    })
    seed_browser_records(flask_app)

    server = make_server("127.0.0.1", 0, flask_app, threaded=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        with sync_playwright() as playwright:
            if browser_name == "chrome":
                browser = playwright.chromium.launch(channel="chrome", headless=True)
            elif browser_name == "edge":
                browser = playwright.chromium.launch(channel="msedge", headless=True)
            else:
                browser = playwright.firefox.launch(headless=True)

            try:
                page = browser.new_page(viewport={"width": 1365, "height": 900})
                login(page, "admin", ADMIN_PASSWORD, base_url)
                assert page.get_by_role("heading", name="Component inventory").is_visible()

                # Search works through the visible inventory search control.
                page.get_by_label("Search components").fill("Arduino Uno R3")
                page.get_by_label("Search components").press("Enter")
                assert page.get_by_text("Arduino Uno R3", exact=True).first.is_visible()

                # Filters retain the selected category/supplier/status across pages.
                page.goto(
                    f"{base_url}/components?category=Browser%20Matrix&"
                    "supplier=Browser%20Matrix%20Supplier&status=In%20Stock"
                )
                assert page.get_by_text("Page 1 of 2").is_visible()
                page.get_by_role("link", name="Next").click()
                assert page.get_by_text("Page 2 of 2").is_visible()
                assert "category=Browser+Matrix" in page.url or "category=Browser%20Matrix" in page.url
                assert "supplier=Browser+Matrix+Supplier" in page.url or "supplier=Browser%20Matrix%20Supplier" in page.url

                # Usability screen path: inventory -> add form -> saved component details.
                page.goto(f"{base_url}/components")
                page.get_by_role("link", name="Add component").click()
                assert page.get_by_role("heading", name="Add component").is_visible()
                page.locator("#sku").fill("BROWSER-SMOKE-001")
                page.locator("#name").fill("Browser Smoke Component")
                page.locator("#category").select_option(label="Microcontrollers")
                page.locator("#supplier").select_option(label="Maker Supplies")
                page.locator("#description").fill("Cross-browser acceptance component")
                page.locator("#quantity").fill("3")
                page.locator("#reorder_level").fill("5")
                page.locator("#unit_price").fill("19.50")
                page.get_by_role("button", name="Save component").click()
                assert page.get_by_text("Low Stock", exact=True).first.is_visible()
                assert page.get_by_role("heading", name="Browser Smoke Component").is_visible()

                # Stock movement persists and recalculates status.
                page.locator("#adjustment").select_option("stock-in")
                page.locator("#stock-quantity").fill("4")
                page.locator("#note").fill("Browser acceptance test")
                page.get_by_role("button", name="Save stock movement").click()
                assert page.get_by_text("In Stock", exact=True).first.is_visible()
                # Issue #21 displays movements as transaction table rows.
                movement = page.get_by_role("row").filter(has_text="Browser acceptance test")
                expect(movement).to_have_count(1)
                for value in ("Stock addition", "+4", "admin", "7"):
                    expect(movement.get_by_role("cell", name=value, exact=True)).to_be_visible()

                # Category and supplier CRUD pages are usable through visible controls.
                page.goto(f"{base_url}/categories")
                page.get_by_role("link", name="Add category").click()
                page.locator("#name").fill("Browser Smoke Category")
                page.get_by_role("button", name="Save category").click()
                assert page.get_by_text("Browser Smoke Category", exact=True).is_visible()

                page.goto(f"{base_url}/suppliers")
                page.get_by_role("link", name="Add supplier").click()
                page.locator("#name").fill("Browser Smoke Supplier")
                page.get_by_role("button", name="Save supplier").click()
                assert page.get_by_text("Browser Smoke Supplier", exact=True).is_visible()

                # Report filter and both export links produce real downloads.
                page.goto(f"{base_url}/reports/availability")
                page.get_by_label("Filter by availability").select_option(label="Out of Stock")
                page.get_by_role("button", name="Apply filters").click()
                assert "status=Out+of+Stock" in page.url or "status=Out%20of%20Stock" in page.url
                with page.expect_download() as csv_download:
                    page.get_by_role("link", name="Download CSV").click()
                csv_file = csv_download.value
                assert csv_file.suggested_filename.endswith(".csv")
                assert Path(csv_file.path()).stat().st_size > 0
                with page.expect_download() as pdf_download:
                    page.get_by_role("link", name="Download PDF").click()
                pdf_file = pdf_download.value
                assert pdf_file.suggested_filename.endswith(".pdf")
                assert Path(pdf_file.path()).stat().st_size > 0

                # Staff can sign in but cannot visit Admin-only management.
                staff_page = browser.new_page(viewport={"width": 1365, "height": 900})
                login(staff_page, "browserstaff", STAFF_PASSWORD, base_url)
                forbidden = staff_page.goto(f"{base_url}/admin/users")
                assert forbidden is not None and forbidden.status == 403
                forbidden_component_form = staff_page.goto(f"{base_url}/components/new")
                assert forbidden_component_form is not None and forbidden_component_form.status == 403
                staff_page.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server_thread.join(timeout=2)
        server.server_close()
        TEMP_DIR.cleanup()

    print(f"PASS: Sprint 1 browser acceptance flow completed in {browser_name}.")


if __name__ == "__main__":
    run()
