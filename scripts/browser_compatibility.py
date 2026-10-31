#!/usr/bin/env python3
"""Issue #13 acceptance against vendor stable browsers, with retained evidence.

Install requirements-browser.txt. Set ESIMS_BROWSER=chrome|edge|firefox.
Selenium Manager downloads the matching browser/driver when necessary. Each run
uses a temporary database and isolated browser profile; normal inventory is untouched.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
import threading
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CHROME_RELEASES = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json"
EDGE_RELEASES = "https://edgeupdates.microsoft.com/api/products?view=enterprise"
FIREFOX_RELEASES = "https://product-details.mozilla.org/1.0/firefox_versions.json"


def latest_stable(browser):
    url = {"chrome": CHROME_RELEASES, "edge": EDGE_RELEASES, "firefox": FIREFOX_RELEASES}[browser]
    with urllib.request.urlopen(url, timeout=60) as response:
        metadata = json.load(response)
    if browser == "chrome":
        version = metadata["channels"]["Stable"]["version"]
    elif browser == "firefox":
        version = metadata["LATEST_FIREFOX_VERSION"]
    else:
        system = {"Windows": "Windows", "Linux": "Linux", "Darwin": "MacOS"}[platform.system()]
        architecture = "arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "x64"
        releases = [release["ProductVersion"] for product in metadata if product["Product"] == "Stable"
                    for release in product["Releases"]
                    if release["Platform"] == system and release["Architecture"] == architecture]
        version = max(releases, key=lambda item: tuple(map(int, item.split("."))))
    return version, url


def launch(browser, version, downloads):
    options = {"chrome": webdriver.ChromeOptions, "edge": webdriver.EdgeOptions,
               "firefox": webdriver.FirefoxOptions}[browser]()
    options.browser_version = version
    if browser == "firefox":
        options.add_argument("-headless")
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.dir", str(downloads))
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/pdf")
        options.set_preference("pdfjs.disabled", True)
    else:
        options.add_argument("--headless=new")
        options.add_argument("--disable-dev-shm-usage")
        options.add_experimental_option("prefs", {
            "download.default_directory": str(downloads), "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
        })
    driver = {"chrome": webdriver.Chrome, "edge": webdriver.Edge, "firefox": webdriver.Firefox}[browser](options=options)
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    driver.set_window_size(1365, 1000)
    return driver


def run():
    browser = os.environ.get("ESIMS_BROWSER", "chrome").lower()
    if browser not in {"chrome", "edge", "firefox"}:
        raise SystemExit("ESIMS_BROWSER must be chrome, edge, or firefox")
    output = Path(os.environ.get("ESIMS_EVIDENCE_DIR", ROOT / "instance" / "browser-evidence")) / browser
    output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("SE_CACHE_PATH", str(ROOT / "instance" / "selenium-cache"))
    os.environ.setdefault("SE_TIMEOUT", "120")
    os.environ.setdefault("SE_AVOID_STATS", "true")
    os.environ.setdefault("SE_SKIP_DRIVER_IN_PATH", "true")
    evidence = {
        "browser": browser, "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(), "result": "FAIL",
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "checks": [], "primary_screens": [], "screenshots": [], "layout_checks": [],
    }
    driver = server = server_thread = None
    temporary = tempfile.TemporaryDirectory(prefix="esims-compatibility-")
    try:
        evidence["step"] = "resolve stable release"
        version, source = latest_stable(browser)
        evidence.update(expected_stable_version=version, release_source=source)
        evidence["step"] = "start stable browser"
        driver = launch(browser, version, Path(temporary.name))
        evidence["browser_version"] = driver.capabilities["browserVersion"]
        assert evidence["browser_version"] == version, "Browser does not match the vendor stable release"
        evidence["user_agent"] = driver.execute_script("return navigator.userAgent")
        os.environ["APP_ENV"] = "development"
        os.environ["SECRET_KEY"] = "issue13-browser-test-only"
        os.environ["DATABASE_PATH"] = str(Path(temporary.name) / "inventory.sqlite")
        for key in ("ADMIN_USERNAME", "ADMIN_EMAIL", "ADMIN_PASSWORD"):
            os.environ.pop(key, None)
        from app import create_app, get_db
        from flask import request
        application = create_app({"TESTING": True, "DATABASE": os.environ["DATABASE_PATH"]})
        measure_creation = False

        @application.after_request
        def record_creation_screen(response):
            if measure_creation and response.status_code == 200 and response.mimetype == "text/html":
                evidence["primary_screens"].append(request.path)
            return response

        with application.app_context():
            db = get_db()
            db.execute("INSERT INTO categories (name) VALUES ('Browser Matrix')")
            db.execute("INSERT INTO suppliers (name) VALUES ('Browser Matrix Supplier')")
            db.executemany("""INSERT INTO components
                (sku,name,category,supplier,quantity,reorder_level,unit_price)
                VALUES (?,?,'Browser Matrix','Browser Matrix Supplier',20,5,1)""",
                [(f"BROWSE-{i:03d}", f"Browser Pagination Component {i:02d}") for i in range(15)])
            db.execute("INSERT INTO users (username,email,password_hash,role) VALUES (?,?,?,'Staff')",
                       ("browserstaff", "staff@example.invalid", generate_password_hash("BrowserStaff123!")))
            db.commit()
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        server = make_server("127.0.0.1", 0, application, threaded=True)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        wait = WebDriverWait(driver, 15)

        def visible(selector):
            return wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))

        def fill(identifier, value):
            element = visible(f"#{identifier}")
            element.clear()
            element.send_keys(value)

        def click(text, tag="button"):
            # Match normalized text, including decorative child spans in Add component.
            wait.until(EC.element_to_be_clickable((By.XPATH, f"//{tag}[contains(normalize-space(.), '{text}')]"))).click()

        def heading(text):
            wait.until(lambda _: visible("h1").text == text)

        def passed(name):
            evidence["checks"].append(name)
            print(f"PASS {browser} {version}: {name}", flush=True)

        def snapshot(name):
            file = f"{name}.png"
            driver.save_screenshot(str(output / file))
            evidence["screenshots"].append(file)

        def layout(name):
            dimensions = driver.execute_script("return {width:innerWidth, height:innerHeight, documentWidth:document.documentElement.scrollWidth}")
            evidence["layout_checks"].append({"screen": name, **dimensions})
            snapshot(name)
            assert dimensions["documentWidth"] <= dimensions["width"] + 1, f"Page overflows horizontally: {name} {dimensions}"

        def login(identity, password):
            driver.get(base + "/login")
            fill("identity", identity)
            fill("password", password)
            click("Sign in")
            heading("Component inventory")

        evidence["step"] = "login, search and combined filters"
        login("admin", "ChangeMe123!")
        search = visible("input[name=q]")
        search.send_keys("Arduino Uno R3", Keys.ENTER)
        assert "Arduino Uno R3" in visible("tbody").text
        driver.get(base + "/components")
        for name, value in [("category", "Browser Matrix"), ("supplier", "Browser Matrix Supplier"), ("status", "In Stock")]:
            Select(visible(f"select[name={name}]")).select_by_visible_text(value)
        click("Apply")
        assert "Page 1 of 2" in visible(".table-footer").text
        click("Next", "a")
        assert "Page 2 of 2" in visible(".table-footer").text
        for key in ("category=", "supplier=", "status="):
            assert key in driver.current_url
        passed("login, search, combined filters and pagination")

        evidence["step"] = "three-screen component creation"
        measure_creation = True
        driver.get(base + "/components")
        layout("01-inventory-desktop")
        click("Add component", "a")
        heading("Add component")
        visible("#sku").send_keys(Keys.TAB)
        assert driver.switch_to.active_element.get_attribute("id") == "name"
        for identifier, value in [("sku", "BROWSER-SMOKE-001"), ("name", "Browser Smoke Component"),
                                  ("description", "Issue 13 browser acceptance"), ("quantity", "3"),
                                  ("reorder_level", "5"), ("unit_price", "19.50")]:
            fill(identifier, value)
        Select(visible("#category")).select_by_visible_text("Microcontrollers")
        Select(visible("#supplier")).select_by_visible_text("Maker Supplies")
        layout("02-component-form-desktop")
        click("Save component")
        heading("Browser Smoke Component")
        detail_url = driver.current_url
        measure_creation = False
        assert evidence["primary_screens"] == ["/components", "/components/new", urlparse(detail_url).path]
        assert "Low Stock" in visible(".detail-stats-grid").text
        layout("03-component-details-desktop")
        passed("component creation in three primary screens; keyboard focus and persisted low-stock status")

        evidence["step"] = "component editing and stock movements"
        click("Edit details", "a")
        fill("description", "Edited in stable browser")
        click("Save component")
        heading("Browser Smoke Component")
        assert "Edited in stable browser" in visible(".detail-heading").text
        for kind, quantity, balance, note in [("stock-in", "4", "7", "Browser stock-in"), ("stock-out", "2", "5", "Browser stock-out")]:
            Select(visible("#adjustment")).select_by_value(kind)
            fill("stock-quantity", quantity)
            fill("note", note)
            click("Save stock movement")
            row = wait.until(lambda _: next((r for r in driver.find_elements(By.CSS_SELECTOR, ".history-panel tbody tr") if note in r.text), None))
            assert row.find_elements(By.TAG_NAME, "td")[4].text == balance
        Select(visible("#adjustment")).select_by_value("stock-out")
        fill("stock-quantity", "999")
        click("Save stock movement")
        assert "exceeds available stock" in visible(".flash-error").text
        assert visible(".detail-stat strong").text.startswith("5 ")
        passed("editing, stock-in/out, resulting balances and oversell rejection")

        evidence["step"] = "catalogue creation and report downloads"
        for path, singular in [("categories", "category"), ("suppliers", "supplier")]:
            driver.get(base + "/" + path)
            click("Add " + singular, "a")
            fill("name", "Browser Smoke " + singular.title())
            click("Save " + singular)
            assert "Browser Smoke " + singular.title() in visible("tbody").text
        driver.get(base + "/reports/availability")
        Select(visible("select[name=status]")).select_by_visible_text("Out of Stock")
        click("Apply filters")
        assert "Raspberry Pi Pico" in visible("tbody").text
        for label, filename, signature in [("Download CSV", "availability-report.csv", b"SKU"),
                                             ("Download PDF", "availability-report.pdf", b"%PDF")]:
            click(label, "a")
            file = Path(temporary.name) / filename
            wait.until(lambda _: file.exists() and file.stat().st_size > 0)
            assert file.read_bytes().startswith(signature)
        passed("category/supplier creation and filtered CSV/PDF downloads")

        evidence["step"] = "form validation and narrow layout"
        driver.get(base + "/components/new")
        click("Save component")
        assert driver.execute_script("return document.querySelector('#sku').validity.valueMissing")
        assert urlparse(driver.current_url).path == "/components/new"
        driver.set_window_size(500, 1000)
        for path, name in [("/components", "04-inventory-narrow"), ("/components/new", "05-component-form-narrow"),
                           (urlparse(detail_url).path, "06-component-details-narrow")]:
            driver.get(base + path)
            visible("h1")
            layout(name)
        passed("required-field validation and narrow inventory/form/detail layout")

        evidence["step"] = "staff permissions and usable stock workflow"
        click("Sign out")
        login("browserstaff", "BrowserStaff123!")
        assert not driver.find_elements(By.CSS_SELECTOR, "a[href='/components/new']")
        for path in ("/components/new", "/admin/users", "/reports/availability"):
            status = driver.execute_async_script("const done=arguments[arguments.length-1]; fetch(arguments[0]).then(r=>done(r.status)).catch(()=>done(0))", base + path)
            assert status == 403, f"Staff access to {path}: {status}"
        driver.get(detail_url)
        Select(visible("#adjustment")).select_by_value("stock-in")
        fill("stock-quantity", "1")
        fill("note", "Staff browser movement")
        click("Save stock movement")
        assert "Staff browser movement" in visible(".history-panel tbody").text
        assert "browserstaff" in visible(".history-panel tbody").text
        passed("staff search/detail/stock operations and Admin-only access restrictions")
        evidence["result"] = "PASS"
    except Exception:
        evidence["error"] = traceback.format_exc()
        if driver is not None:
            try:
                driver.save_screenshot(str(output / "failure.png"))
                evidence["screenshots"].append("failure.png")
            except Exception:
                pass
        raise
    finally:
        evidence["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (output / "results.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        try:
            if driver is not None:
                driver.quit()
        finally:
            if server is not None:
                server.shutdown()
                server_thread.join(timeout=5)
                server.server_close()
            temporary.cleanup()
    print(f"PASS: {browser} {version}; evidence: {output}", flush=True)


if __name__ == "__main__":
    run()
