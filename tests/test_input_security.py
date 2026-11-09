"""SEC-003: malicious input remains data; invalid input cannot change inventory."""
import csv
import io
import sqlite3
from html.parser import HTMLParser

import pytest
from werkzeug.datastructures import MultiDict

from app import create_app, get_db
from input_validation import MAX_SQLITE_INTEGER
from inventory_service import adjust_stock, validate_component_form


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "WTF_CSRF_ENABLED": False,
                       "SECRET_KEY": "security-tests-only", "DATABASE": str(tmp_path / "security.sqlite")})


@pytest.fixture()
def client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
    return client


def component(**changes):
    return {"sku": "SEC-001", "name": "Security test board", "description": "",
            "category": "Microcontrollers", "supplier": "Maker Supplies",
            "quantity": "3", "reorder_level": "5", "unit_price": "19.50", **changes}


def snapshot(app):
    with sqlite3.connect(app.config["DATABASE"]) as db:
        return {table: db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
                for table in ("components", "categories", "suppliers", "users", "inventory_transactions")}


class ParsedHTML(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.text = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def assert_inert_html(response):
    parsed = ParsedHTML(response.get_data(as_text=True))
    assert not any(tag in {"img", "svg", "iframe", "object", "base"} for tag, _ in parsed.tags)
    assert not any(key.lower().startswith("on") for _, attrs in parsed.tags for key in attrs)
    assert all(attrs.get("src") == "/static/app.js" for tag, attrs in parsed.tags if tag == "script")
    return parsed


SQL_PAYLOADS = ["' OR 1=1 --", "x'); DROP TABLE components; --", "' UNION SELECT 1,2,3 --"]
XSS_PAYLOADS = ["<script>window.__securityExecuted=1</script>",
                '<img src=x onerror="window.__securityExecuted=1">',
                '</textarea><svg onload="window.__securityExecuted=1">',
                '{{7*7}} & <b>plain text</b>']


@pytest.mark.parametrize("payload", SQL_PAYLOADS)
def test_sql_payload_cannot_authenticate_or_change_data(app, payload):
    anonymous = app.test_client()
    before = snapshot(app)
    response = anonymous.post("/login", data={"identity": payload, "password": "ChangeMe123!"})
    assert response.status_code == 401
    with anonymous.session_transaction() as session:
        assert "user_id" not in session
    assert snapshot(app) == before


@pytest.mark.parametrize("payload", SQL_PAYLOADS)
def test_sql_payload_is_bound_in_search_filters_and_writes(client, app, payload):
    before = snapshot(app)
    for query in ({"q": payload}, {"category": payload}, {"supplier": payload}):
        response = client.get("/components", query_string=query)
        assert response.status_code == 200
        assert "No components found" in response.get_data(as_text=True)
    for path in ("/reports/availability", "/reports/availability.csv", "/reports/availability.pdf"):
        assert client.get(path, query_string={"category": payload}).status_code == 200
    assert snapshot(app) == before
    response = client.post("/categories/new", data={"name": payload}, follow_redirects=True)
    assert response.status_code == 200
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM categories WHERE name=?", (payload,)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM components").fetchone()[0] == len(before["components"])
    response = client.post("/components/new", data=component(name=payload), follow_redirects=True)
    assert response.status_code == 200
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT name FROM components WHERE sku='SEC-001'").fetchone()[0] == payload


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_stored_component_and_stock_note_are_escaped(client, app, payload):
    response = client.post("/components/new", data=component(name=payload, description=payload), follow_redirects=True)
    assert response.status_code == 200
    parsed = assert_inert_html(response)
    assert payload in "".join(parsed.text)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        row = db.execute("SELECT id,name,description FROM components WHERE sku='SEC-001'").fetchone()
    assert row[1:] == (payload, payload)
    response = client.post(f"/components/{row[0]}/stock", data={"adjustment": "stock-in", "quantity": "1", "note": payload}, follow_redirects=True)
    assert response.status_code == 200
    assert payload in "".join(assert_inert_html(response).text)
    for path in ("/components?q=SEC-001", "/reports/availability"):
        assert_inert_html(client.get(path))
    pdf = client.get("/reports/availability.pdf")
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")


@pytest.mark.parametrize("path", ["/categories/new", "/suppliers/new"])
def test_stored_catalogue_and_option_attributes_are_escaped(client, path):
    payload = '<svg onload="alert(1)">'
    response = client.post(path, data={"name": payload}, follow_redirects=True)
    assert response.status_code == 200
    assert payload in "".join(assert_inert_html(response).text)
    parsed = assert_inert_html(client.get("/components/new"))
    assert any(tag == "option" and attrs.get("value") == payload for tag, attrs in parsed.tags)


def test_user_names_are_plain_text_and_passwords_remain_secret(client, app):
    username = '<img src=x onerror="alert(1)">'
    response = client.post("/admin/users", data={"username": username, "email": "safe@example.test",
                                               "password": "  Pa\u00dfword'<&>123!  ", "role": "Staff"}, follow_redirects=True)
    assert response.status_code == 200
    assert username in "".join(assert_inert_html(response).text)
    assert "Pa\u00dfword" not in response.get_data(as_text=True)
    client.post("/logout")
    response = client.post("/login", data={"identity": username, "password": "  Pa\u00dfword'<&>123!  "}, follow_redirects=True)
    assert response.status_code == 200
    assert_inert_html(response)
    assert client.get("/admin/users").status_code == 403


@pytest.mark.parametrize("payload", ['" autofocus onfocus="alert(1)', '<script>alert(1)</script>'])
def test_reflected_form_and_search_values_cannot_inject_attributes(client, payload):
    response = client.post("/components/new", data=component(sku=payload))
    assert response.status_code == 400
    parsed = assert_inert_html(response)
    assert any(attrs.get("id") == "sku" and attrs.get("value") == payload for _, attrs in parsed.tags)
    response = client.get("/components", query_string={"q": payload})
    parsed = assert_inert_html(response)
    assert any(attrs.get("name") == "q" and attrs.get("value") == payload for _, attrs in parsed.tags)


def test_csv_xss_content_and_error_report_are_inert(client, app):
    payload = '<img src=x onerror="alert(1)">'
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["sku", "name", "description", "category", "supplier", "quantity", "reorder_level", "unit_price"])
    writer.writerow(["SEC-CSV", payload, payload, "Microcontrollers", "Maker Supplies", 1, 5, 3.50])
    writer.writerow([payload, "Invalid SKU", "", "Microcontrollers", "Maker Supplies", 1, 5, 3.50])
    response = client.post("/components/import", data={"file": (io.BytesIO(buffer.getvalue().encode()), "input.csv")})
    assert response.status_code == 200
    assert "1 imported" in response.get_data(as_text=True) and "1 rejected" in response.get_data(as_text=True)
    assert_inert_html(response)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        component_id = db.execute("SELECT id FROM components WHERE sku='SEC-CSV'").fetchone()[0]
    assert_inert_html(client.get(f"/components/{component_id}"))


@pytest.mark.parametrize("value", ["\u00b2", "\u0661", "1_000", "+1", "1e3", "NaN", "-1", "0", "9223372036854775808", "9" * 5000],
                         ids=["superscript", "arabic-digit", "underscore", "plus", "exponent", "nan", "negative", "zero", "overflow", "huge"])
def test_malformed_stock_quantity_returns_400_without_writes(client, app, value):
    before = snapshot(app)
    response = client.post("/components/1/stock", data={"adjustment": "stock-in", "quantity": value})
    assert response.status_code == 400
    assert "Stock quantity" in response.get_data(as_text=True)
    assert snapshot(app) == before


def test_stock_balance_overflow_rolls_back_and_service_also_rejects_it(client, app):
    with sqlite3.connect(app.config["DATABASE"]) as db:
        db.execute("UPDATE components SET quantity=? WHERE id=1", (MAX_SQLITE_INTEGER,))
    before = snapshot(app)
    response = client.post("/components/1/stock", data={"adjustment": "stock-in", "quantity": "1"})
    assert response.status_code == 400 and "resulting stock exceeds" in response.get_data(as_text=True)
    assert snapshot(app) == before
    with app.app_context():
        with pytest.raises(ValueError, match="resulting stock exceeds"):
            adjust_stock(get_db(), component_id=1, user_id=1, adjustment="stock-in", quantity=1)
        with pytest.raises(ValueError, match="quantity exceeds"):
            adjust_stock(get_db(), component_id=1, user_id=1, adjustment="stock-in", quantity=MAX_SQLITE_INTEGER + 1)
    assert snapshot(app) == before


@pytest.mark.parametrize("query", [{"page": "9" * 200}, {"page": "abc"}, {"page": "-1"}, {"page": "0"},
                                 {"status": "' OR 1=1 --"}, {"q": "x" * 101}, {"category": "x" * 81}, {"supplier": "x" * 121}],
                         ids=["overflow-page", "nonnumeric-page", "negative-page", "zero-page", "status", "search-length", "category-length", "supplier-length"])
def test_invalid_inventory_filters_are_rejected(client, query):
    response = client.get("/components", query_string=query)
    assert response.status_code == 400
    assert "Invalid request" in response.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/reports/availability", "/reports/availability.csv", "/reports/availability.pdf"])
def test_invalid_report_filters_are_rejected_consistently(client, path):
    assert client.get(path, query_string={"status": "invalid"}).status_code == 400
    assert client.get(path, query_string={"supplier": "x" * 121}).status_code == 400


@pytest.mark.parametrize("field, value", [("username", "x" * 81), ("username", "a\nb"), ("email", "bad@@example.test"),
                                       ("email", "a@-host.test"), ("email", "a@host..test"), ("email", "a b@example.test"),
                                       ("password", "x" * 1025), ("role", "Staff' OR 1=1 --")])
def test_invalid_account_fields_cannot_create_users(client, app, field, value):
    data = {"username": "new-user", "email": "new@example.test", "password": "ValidPassword123!", "role": "Staff"}
    data[field] = value
    before = snapshot(app)
    response = client.post("/admin/users", data=data)
    assert response.status_code == 400
    assert "ValidPassword123!" not in response.get_data(as_text=True)
    assert snapshot(app) == before


@pytest.mark.parametrize("path, data", [("/components/new", component(name="bad\x00name")),
                                      ("/categories/new", {"name": "bad\x1bname"}),
                                      ("/suppliers/new", {"name": "bad\x7fname"}),
                                      ("/components/1/stock", {"adjustment": "stock-in", "quantity": "1", "note": "x" * 251})])
def test_invalid_text_is_rejected_without_silent_truncation(client, app, path, data):
    before = snapshot(app)
    assert client.post(path, data=data).status_code == 400
    assert snapshot(app) == before


def test_duplicate_parameters_json_and_huge_ids_are_rejected(client, app):
    before = snapshot(app)
    assert client.get("/components?q=one&q=two").status_code == 400
    data = MultiDict([*component().items(), ("quantity", "999")])
    assert client.post("/components/new", data=data).status_code == 400
    assert client.post("/components/new", json=component()).status_code == 415
    for path in ("/components/", "/categories/", "/suppliers/"):
        suffix = "" if path == "/components/" else "/edit"
        assert client.get(path + "9" * 100 + suffix).status_code == 404
    assert snapshot(app) == before


def test_oversized_request_is_413_and_csrf_still_protects_mutations(client, app):
    before = snapshot(app)
    response = client.post("/components/new", data="name=" + "x" * (2 * 1024 * 1024), content_type="application/x-www-form-urlencoded")
    assert response.status_code == 413
    app.config["WTF_CSRF_ENABLED"] = True
    for path, data in [("/components/new", component()), ("/components/1/stock", {"adjustment": "stock-in", "quantity": "1"}),
                       ("/categories/new", {"name": "Valid"}), ("/admin/users", {"username": "new"}), ("/logout", {})]:
        assert client.post(path, data=data).status_code == 400
    assert snapshot(app) == before
    with client.session_transaction() as session:
        assert session["user_id"] == 1


@pytest.mark.parametrize("data", [{"name": "x" * (128 * 1024 + 1)},
                                 {f"field-{index}": "x" for index in range(33)}],
                         ids=["form-memory-limit", "multipart-part-limit"])
def test_multipart_limits_are_enforced_before_writes(client, app, data):
    before = snapshot(app)
    response = client.post("/components/new", data=data, content_type="multipart/form-data")
    assert response.status_code == 413
    assert snapshot(app) == before


def test_headers_and_external_delete_confirmation_preserve_safe_rendering(client):
    for path in ("/components", "/components/1", "/export/components.csv", "/reports/availability.pdf"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        policy = response.headers["Content-Security-Policy"]
        assert "script-src 'self';" in policy and "object-src 'none'" in policy
        assert "unsafe-inline" not in policy.split("script-src", 1)[1].split(";", 1)[0]
        assert "unsafe-inline" not in policy.split("style-src", 1)[1].split(";", 1)[0]
    for path in ("/", "/components/1", "/categories", "/suppliers"):
        assert b"style=" not in client.get(path).data
    for path in ("/components/1", "/categories", "/suppliers"):
        page = client.get(path)
        parsed = assert_inert_html(page)
        assert any(tag == "form" and attrs.get("data-confirm") for tag, attrs in parsed.tags)
    assert client.get("/static/app.js").status_code == 200


@pytest.mark.parametrize("field, value", [("quantity", "\u00b2"), ("quantity", "1_000"), ("reorder_level", "\u0661"),
                                       ("unit_price", "1_0"), ("name", None), ("description", "bad\x00text")])
def test_shared_component_validation_rejects_malformed_csv_and_form_values(field, value):
    values, error = validate_component_form(component(**{field: value}))
    assert values is None and error


def test_valid_unicode_punctuation_and_large_zero_padded_numbers_still_work(client):
    name = "R\u00e9sistance 3 < 5 & O'Reilly"
    response = client.post("/components/new", data=component(name=name, description="Line one\nLine two\tvalue", quantity="0" * 5000 + "3"), follow_redirects=True)
    assert response.status_code == 200
    assert name in "".join(assert_inert_html(response).text)
    assert "3 units" in "".join(ParsedHTML(response.get_data(as_text=True)).text)


def test_cli_uses_account_validation_before_database_writes(app):
    before = snapshot(app)
    result = app.test_cli_runner().invoke(args=["create-admin", "--username", "bad\nname", "--email", "bad@@mail", "--password", "ValidPassword123!"])
    assert result.exit_code != 0
    assert snapshot(app) == before
