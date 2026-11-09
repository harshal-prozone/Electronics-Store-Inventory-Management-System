#!/usr/bin/env python3
"""Issue #13 acceptance against vendor stable browsers, with retained evidence.

Install requirements-browser.txt. Set ESIMS_BROWSER=chrome|edge|firefox.
Selenium Manager downloads the matching browser/driver when necessary. Each run
uses a temporary database and isolated browser profile; normal inventory is untouched.
"""
from __future__ import annotations

import hashlib
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
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.service import Service as FirefoxService
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


def launch(browser, version, downloads, output):
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
        if os.environ.get("ESIMS_CHROMIUM_NO_SANDBOX") == "1":
            # Only opted into by the isolated hosted-CI job, not normal runs.
            options.add_argument("--no-sandbox")
        options.add_experimental_option("prefs", {
            "download.default_directory": str(downloads), "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
        })
    service_class = {"chrome": ChromeService, "edge": EdgeService, "firefox": FirefoxService}[browser]
    service = service_class(log_output=str(output / "webdriver.log"))
    driver = {"chrome": webdriver.Chrome, "edge": webdriver.Edge, "firefox": webdriver.Firefox}[browser](options=options, service=service)
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
    os.environ.setdefault("SE_TIMEOUT", "300")
    os.environ.setdefault("SE_AVOID_STATS", "true")
    os.environ.setdefault("SE_SKIP_DRIVER_IN_PATH", "true")
    evidence = {
        "browser": browser, "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(), "result": "FAIL",
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "chromium_no_sandbox": browser != "firefox" and os.environ.get("ESIMS_CHROMIUM_NO_SANDBOX") == "1",
        "webdriver_log": "webdriver.log",
        "checks": [], "primary_screens": [], "screenshots": [], "layout_checks": [],
    }
    driver = server = server_thread = None
    temporary = tempfile.TemporaryDirectory(prefix="esims-compatibility-")
    try:
        evidence["step"] = "resolve stable release"
        version, source = latest_stable(browser)
        evidence.update(expected_stable_version=version, release_source=source)
        evidence["step"] = "start stable browser"
        driver = launch(browser, version, Path(temporary.name), output)
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

        def document_token():
            token = uuid.uuid4().hex
            driver.execute_script("window.__esimsDocumentToken = arguments[0]", token)
            return token

        def wait_for_navigation(token):
            # Edge can report detached nodes as a generic inspector error rather
            # than StaleElementReferenceException. Observe the new document
            # without querying any WebElement belonging to the previous one.
            wait.until(lambda _: driver.execute_script("return window.__esimsDocumentToken !== arguments[0]", token))
            wait.until(lambda _: driver.execute_script("return document.readyState") == "complete")

        def click(text, tag="button", navigate=True):
            # Match normalized text, including decorative child spans in Add component.
            target = wait.until(EC.element_to_be_clickable((By.XPATH, f"//{tag}[contains(normalize-space(.), '{text}')]")))
            previous_document = document_token() if navigate else None
            target.click()
            if navigate:
                wait_for_navigation(previous_document)

        def heading(text):
            wait.until(EC.visibility_of_element_located((By.XPATH, f"//h1[normalize-space(.)='{text}']")))

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
        previous_document = document_token()
        search.send_keys("Arduino Uno R3", Keys.ENTER)
        wait_for_navigation(previous_document)
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
        xss_description = '<img src=x onerror="window.__securityExecuted=1"><script>window.__securityExecuted=1</script>'
        for identifier, value in [("sku", "BROWSER-SMOKE-001"), ("name", "Browser Smoke Component"),
                                  ("description", xss_description), ("quantity", "3"),
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
        assert visible(".detail-heading-text p").text == xss_description
        assert not driver.find_elements(By.CSS_SELECTOR, ".detail-heading-text img, .detail-heading-text script")
        assert driver.execute_script("return window.__securityExecuted === undefined")
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

        evidence["step"] = "CSV import and recorded adjustments"
        driver.get(base + "/components")
        click("Import CSV", "a")
        click("Download CSV template", "a", navigate=False)
        template = Path(temporary.name) / "inventory-import-template.csv"
        wait.until(lambda _: template.exists() and template.stat().st_size > 0)
        assert "sku,name,description,category,supplier,quantity,reorder_level,unit_price" in template.read_text(encoding="utf-8")
        upload = Path(temporary.name) / "inventory-upload.csv"
        upload.write_text(
            "sku,name,category,supplier,quantity,reorder_level,unit_price\n"
            "BROWSER-IMPORT-001,CSV browser board,Microcontrollers,Maker Supplies,2,5,9.50\n"
            "BROWSER-SMOKE-001,Browser Smoke Component,Microcontrollers,Maker Supplies,6,5,19.50\n"
            "BROWSER-INVALID,Invalid board,Microcontrollers,Maker Supplies,invalid,5,9.50\n",
            encoding="utf-8",
        )
        visible("#csv-file").send_keys(str(upload))
        click("Import inventory")
        results = visible("section[aria-labelledby='import-results-heading']").text
        assert "2 imported" in results and "1 created, 1 updated" in results and "1 rejected" in results
        assert "BROWSER-INVALID" in results and "whole numbers" in results
        snapshot("07-csv-import-results")
        driver.get(detail_url)
        row = wait.until(lambda _: next((r for r in driver.find_elements(By.CSS_SELECTOR, ".history-panel tbody tr")
                                        if "CSV inventory import, line 3" in r.text), None))
        cells = row.find_elements(By.TAG_NAME, "td")
        assert cells[1].text == "Adjustment" and cells[4].text == "6"
        passed("CSV template download, mixed create/update/rejection and adjustment history")

        evidence["step"] = "stock alerts on dashboard"
        driver.get(base + "/")
        assert "Recent stock alerts" in driver.page_source
        assert "Browser Smoke Component" in driver.page_source
        assert "Current low-stock items" in driver.page_source
        bars = driver.find_elements(By.CSS_SELECTOR, ".dashboard-layout progress.dashboard-bar-fill")
        assert len(bars) == 3
        assert all(0 <= float(bar.get_attribute("value")) <= 100 for bar in bars)
        assert all(bar.size["width"] > 0 for bar in bars)
        category_bars = driver.find_elements(By.CSS_SELECTOR, ".category-chart-panel progress")
        assert category_bars and "Stock by category" in driver.page_source
        assert all(0 <= float(bar.get_attribute("value")) <= 100 for bar in category_bars)
        assert not driver.find_elements(By.CSS_SELECTOR, "[style]")
        passed("stock alerts and inline-style-free availability and category charts render")

        evidence["step"] = "catalogue creation and report downloads"
        for path, singular in [("categories", "category"), ("suppliers", "supplier")]:
            driver.get(base + "/" + path)
            click("Add " + singular, "a")
            fill("name", "Browser Smoke " + singular.title())
            if singular == "supplier":
                fill("contact_email", "supplier@example.invalid")
                fill("phone", "+91 12345")
            click("Save " + singular)
            assert "Browser Smoke " + singular.title() in visible("tbody").text
            if singular == "supplier":
                assert "supplier@example.invalid" in visible("tbody").text
                assert "+91 12345" in visible("tbody").text
        driver.get(base + "/reports/availability")
        Select(visible("select[name=status]")).select_by_visible_text("Out of Stock")
        click("Apply filters")
        assert "Raspberry Pi Pico" in visible("tbody").text
        for label, filename, signature in [("Download CSV", "availability-report.csv", b"SKU"),
                                             ("Download PDF", "availability-report.pdf", b"%PDF")]:
            click(label, "a", navigate=False)
            file = Path(temporary.name) / filename
            wait.until(lambda _: file.exists() and file.stat().st_size > 0)
            assert file.read_bytes().startswith(signature)
        passed("category/supplier creation and filtered CSV/PDF downloads")

        evidence["step"] = "form validation and narrow layout"
        driver.get(base + "/components/new")
        click("Save component", navigate=False)
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
        assert driver.find_elements(By.CSS_SELECTOR, "a[href='/components/new']")
        assert driver.find_elements(By.CSS_SELECTOR, "a[href='/reports/availability']")
        assert not driver.find_elements(By.CSS_SELECTOR, "a[href='/components/import']")
        for path in ("/components/import", "/admin/users", "/admin/audit-log", "/categories/new", "/suppliers/new"):
            status = driver.execute_async_script("const done=arguments[arguments.length-1]; fetch(arguments[0]).then(r=>done(r.status)).catch(()=>done(0))", base + path)
            assert status == 403, f"Staff access to {path}: {status}"
        evidence["admin_primary_screens"] = evidence["primary_screens"]
        evidence["primary_screens"] = []
        measure_creation = True
        driver.get(base + "/components")
        click("Add component", "a")
        for identifier, value in [("sku", "BROWSER-STAFF-001"), ("name", "Browser Staff Component"),
                                  ("quantity", "2"), ("reorder_level", "5"), ("unit_price", "10")]:
            fill(identifier, value)
        Select(visible("#category")).select_by_visible_text("Microcontrollers")
        Select(visible("#supplier")).select_by_visible_text("Maker Supplies")
        click("Save component")
        heading("Browser Staff Component")
        staff_detail = urlparse(driver.current_url).path
        measure_creation = False
        assert evidence["primary_screens"] == ["/components", "/components/new", staff_detail]
        assert not driver.find_elements(By.XPATH, "//button[contains(., 'Delete component')]")
        click("Edit details", "a")
        fill("description", "Edited by browser staff")
        click("Save component")
        assert "Edited by browser staff" in visible(".detail-heading").text
        driver.get(base + "/reports/availability")
        Select(visible("select[name=status]")).select_by_visible_text("Low Stock")
        click("Apply filters")
        assert "Browser Staff Component" in visible("tbody").text
        for label, filename, signature in [("Download CSV", "availability-report.csv", b"SKU"),
                                             ("Download PDF", "availability-report.pdf", b"%PDF")]:
            file = Path(temporary.name) / filename
            file.unlink(missing_ok=True)
            click(label, "a", navigate=False)
            wait.until(lambda _: file.exists() and file.stat().st_size > 0)
            assert file.read_bytes().startswith(signature)
        driver.get(detail_url)
        Select(visible("#adjustment")).select_by_value("stock-in")
        fill("stock-quantity", "1")
        fill("note", "Staff browser movement")
        click("Save stock movement")
        assert "Staff browser movement" in visible(".history-panel tbody").text
        assert "browserstaff" in visible(".history-panel tbody").text
        passed("staff three-screen create, edit, filtered CSV/PDF report, stock movement and admin restrictions")

        assert not driver.find_elements(By.CSS_SELECTOR, "a[href='/admin/audit-log']")
        evidence["step"] = "XSS protection and CSP-compatible delete confirmation"
        click("Sign out")
        login("admin", "ChangeMe123!")
        reflected = '\"><img src=x onerror="window.__securityExecuted=1">'
        previous_document = document_token()
        visible("input[name=q]").send_keys(reflected, Keys.ENTER)
        wait_for_navigation(previous_document)
        assert visible("input[name=q]").get_attribute("value") == reflected
        assert not driver.find_elements(By.TAG_NAME, "img")
        assert driver.execute_script("return window.__securityExecuted === undefined")
        driver.get(detail_url)
        click("Delete component", navigate=False)
        wait.until(EC.alert_is_present()).dismiss()
        heading("Browser Smoke Component")
        assert driver.current_url == detail_url
        previous_document = document_token()
        click("Delete component", navigate=False)
        wait.until(EC.alert_is_present()).accept()
        wait_for_navigation(previous_document)
        heading("Component inventory")
        driver.get(base + "/components?q=BROWSER-SMOKE-001")
        assert "No components found" in visible(".empty-cell").text
        passed("stored/reflected XSS remains inert; delete confirmation cancel/accept works under CSP")

        evidence["step"] = "Admin audit review and recorded deletion"
        click("Audit log", "a")
        heading("Audit log")
        assert "component-deleted" in visible("tbody").text
        assert "BROWSER-SMOKE-001" in visible("tbody").text
        Select(visible("select[name=event_type]")).select_by_value("component-deleted")
        Select(visible("select[name=user_id]")).select_by_visible_text("admin")
        click("Apply")
        assert "1 record" in visible("main").text
        assert "admin (#1)" in visible("tbody").text
        assert "PEER IP" in visible("thead").text.upper()
        assert "127.0.0.1" in visible("tbody").text
        assert "stock-adjustment" not in visible("tbody").text
        driver.set_window_size(1365, 1000)
        layout("08-audit-log-desktop")
        driver.set_window_size(500, 1000)
        layout("09-audit-log-narrow")
        passed("Admin-only audit review, event/user filters and attributed component deletion")
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
