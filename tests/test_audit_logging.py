"""Issue #10: security recording, traceability, access and atomicity."""

import sqlite3
from datetime import datetime, timezone

import pytest
from werkzeug.security import generate_password_hash

from app import create_app, get_db, write_audit


@pytest.fixture()
def app(tmp_path):
    application = create_app({
        "TESTING": True, "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "audit-test-only", "DATABASE": str(tmp_path / "audit.sqlite"),
    })
    with application.app_context():
        db = get_db()
        db.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'Staff')",
                   ("employee", "employee@example.com", generate_password_hash("Employee123!")))
        db.commit()
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def authenticate(client, user_id=1):
    with client.session_transaction() as state:
        state["user_id"] = user_id


def records(app, event):
    with app.app_context():
        return get_db().execute("SELECT * FROM audit_log WHERE event_type = ? ORDER BY id", (event,)).fetchall()


def test_authentication_events_timestamp_and_no_secrets(app, client):
    before = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    client.post("/login", data={"identity": "unknown", "password": "DO-NOT-LOG-THIS"})
    failed = records(app, "login-failed")[0]
    assert failed["user_id"] is None
    assert failed["details"] == "identity=unknown"
    assert client.post("/login", data={"identity": "admin", "password": "ChangeMe123!"}).status_code == 302
    success = records(app, "login-success")[0]
    assert success["user_id"] == 1
    assert "username=admin" in success["details"]
    assert before <= datetime.fromisoformat(success["created_at"]) <= datetime.now(timezone.utc).replace(tzinfo=None)
    assert client.post("/logout").status_code == 302
    assert records(app, "logout")[0]["user_id"] == 1
    with app.app_context():
        content = " ".join(row[0] for row in get_db().execute("SELECT details FROM audit_log"))
    for secret in ["DO-NOT-LOG-THIS", "ChangeMe123!", "password_hash", "csrf_token"]:
        assert secret not in content


def test_login_audit_failure_does_not_establish_session(app, client):
    reject_event(app, "login-success")
    with pytest.raises(sqlite3.IntegrityError, match="audit unavailable"):
        client.post("/login", data={"identity": "admin", "password": "ChangeMe123!"})
    with client.session_transaction() as state:
        assert "user_id" not in state


def test_anonymous_and_staff_cannot_read_audit_log(app, client):
    assert client.get("/admin/audit-log").status_code == 302
    assert records(app, "authentication-required")[0]["user_id"] is None
    authenticate(client, 2)
    response = client.get("/admin/audit-log?password=SECRET-QUERY")
    assert response.status_code == 403
    assert response.headers["Cache-Control"] == "no-store"
    event = records(app, "access-denied")[0]
    assert event["user_id"] == 2
    assert event["details"] == "method=GET; endpoint=audit_log; status=403"
    assert "SECRET-QUERY" not in event["details"]
    assert b"login-success" not in response.data
    assert b"Audit log</a>" not in client.get("/components").data


@pytest.mark.parametrize("user_id", [None, 1, 2])
def test_csrf_rejection_is_recorded_even_before_user_loading(app, client, user_id):
    app.config["WTF_CSRF_ENABLED"] = True
    if user_id:
        authenticate(client, user_id)
    response = client.post("/components/1/delete", data={"password": "SECRET-BODY"})
    assert response.status_code == 400
    assert b"security token" in response.data
    event = records(app, "csrf-rejected")[0]
    assert event["user_id"] == user_id
    assert event["details"] == "method=POST; endpoint=component_delete"
    assert not records(app, "component-deleted")


@pytest.mark.parametrize("stale_id", [9999, "malformed", [1], 2**100])
def test_stale_session_is_rejected_safely(app, client, stale_id):
    authenticate(client, stale_id)
    assert client.get("/components").status_code == 302
    assert records(app, "session-rejected")[0]["user_id"] is None
    with client.session_transaction() as state:
        assert "user_id" not in state


def test_component_delete_has_one_attributed_record(app, client):
    authenticate(client)
    with app.app_context():
        sku = get_db().execute("SELECT sku FROM components WHERE id=1").fetchone()[0]
    assert client.post("/components/1/delete").status_code == 302
    event = records(app, "component-deleted")[0]
    assert event["user_id"] == 1
    assert event["created_at"]
    assert event["details"] == f"component_id=1; sku={sku}"
    assert client.post("/components/1/delete").status_code == 404
    assert len(records(app, "component-deleted")) == 1


def reject_event(app, event):
    with app.app_context():
        # event is supplied only by this test module, never by request input.
        get_db().execute(f"""CREATE TRIGGER fail_audit BEFORE INSERT ON audit_log
            WHEN NEW.event_type = '{event}'
            BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END""")
        get_db().commit()


def test_component_delete_rolls_back_if_audit_fails(app, client):
    authenticate(client)
    reject_event(app, "component-deleted")
    with pytest.raises(sqlite3.IntegrityError, match="audit unavailable"):
        client.post("/components/1/delete")
    with app.app_context():
        assert get_db().execute("SELECT deleted_at FROM components WHERE id=1").fetchone()[0] is None
    assert not records(app, "component-deleted")


def test_staff_cannot_delete_component(app, client):
    authenticate(client, 2)
    assert client.post("/components/1/delete").status_code == 403
    assert records(app, "access-denied")[0]["user_id"] == 2
    assert not records(app, "component-deleted")
    with app.app_context():
        assert get_db().execute("SELECT deleted_at FROM components WHERE id=1").fetchone()[0] is None


@pytest.mark.parametrize("kind", ["category", "supplier"])
@pytest.mark.parametrize("failure", [False, True])
def test_catalogue_deletions_are_atomic_and_audited(app, client, kind, failure):
    authenticate(client)
    table = "categories" if kind == "category" else "suppliers"
    with app.app_context():
        db = get_db()
        cursor = db.execute(f"INSERT INTO {table} (name) VALUES ('Unused item')")
        item_id = cursor.lastrowid
        db.commit()
    if failure:
        reject_event(app, f"{kind}-deleted")
        with pytest.raises(sqlite3.IntegrityError, match="audit unavailable"):
            client.post(f"/{table}/{item_id}/delete")
    else:
        assert client.post(f"/{table}/{item_id}/delete").status_code == 302
        assert records(app, f"{kind}-deleted")[0]["user_id"] == 1
    with app.app_context():
        exists = get_db().execute(f"SELECT 1 FROM {table} WHERE id=?", (item_id,)).fetchone()
    assert bool(exists) == failure


def test_account_creation_is_audited_and_atomic(app, client):
    authenticate(client)
    data = {"username": "new-user", "email": "new@example.com", "password": "NewPassword123!", "role": "Admin"}
    reject_event(app, "user-created")
    client.post("/admin/users", data=data)
    with app.app_context():
        assert get_db().execute("SELECT 1 FROM users WHERE username='new-user'").fetchone() is None
        get_db().execute("DROP TRIGGER fail_audit")
        get_db().commit()
    assert client.post("/admin/users", data=data).status_code == 302
    event = records(app, "user-created")[0]
    assert event["user_id"] == 1
    assert "role=Admin" in event["details"]
    assert "NewPassword123!" not in event["details"]


def test_cli_admin_creation_is_audited_without_invented_actor(app):
    result = app.test_cli_runner().invoke(args=["create-admin", "--username", "operator", "--email", "operator@example.com", "--password", "Operator123!"])
    assert result.exit_code == 0
    event = records(app, "user-created")[0]
    assert event["user_id"] is None
    assert "source=create-admin-cli" in event["details"]
    assert "Operator123!" not in event["details"]


@pytest.mark.parametrize("sql", [
    "UPDATE audit_log SET details='forged'", "DELETE FROM audit_log",
    "DELETE FROM users WHERE id=1",
])
def test_database_rejects_history_modification(app, sql):
    with app.app_context():
        write_audit(1, "original", "preserve me")
        with pytest.raises(sqlite3.IntegrityError, match="Audit records cannot"):
            get_db().execute(sql)
        get_db().rollback()
        assert get_db().execute("SELECT details FROM audit_log").fetchone()[0] == "preserve me"


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_no_web_route_can_mutate_audit_records(app, client, method):
    authenticate(client)
    with app.app_context():
        write_audit(1, "original", "preserve me")
    assert getattr(client, method)("/admin/audit-log", data={"details": "forged"}).status_code == 405
    assert records(app, "original")[0]["details"] == "preserve me"


def test_admin_review_filters_order_pagination_and_escaping(app, client):
    authenticate(client)
    with app.app_context():
        for number in range(30):
            write_audit(1, "review-event", f"record-{number:02}")
        write_audit(2, "other-event", "<script>alert('xss')</script>")
    response = client.get("/admin/audit-log")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert b"&lt;script&gt;" in response.data
    assert b"<script>alert" not in response.data
    assert b"employee (#2)" in response.data
    page = client.get("/admin/audit-log?event_type=review-event&user_id=1").get_data(as_text=True)
    assert "30 records" in page and "Page 1 of 2" in page
    assert page.index("record-29") < page.index("record-28")
    assert "record-00" not in page and "other-event</td>" not in page
    assert "event_type=review-event&amp;user_id=1&amp;page=2" in page
    second = client.get("/admin/audit-log?event_type=review-event&user_id=1&page=2").get_data(as_text=True)
    assert "record-00" in second and "record-29" not in second
    assert b"No audit records" in client.get("/admin/audit-log?event_type=' OR 1=1--").data


@pytest.mark.parametrize("query", ["page=-1", "page=1e6", "page=" + "9" * 5000,
                                        "user_id=-1", "user_id=9223372036854775808", "page=1&page=2", "event_type=" + "a" * 81])
def test_malformed_audit_filters_rejected(client, query):
    authenticate(client)
    assert client.get("/admin/audit-log?" + query).status_code == 400


def test_upgrade_preserves_existing_records_and_installs_protection(app):
    with app.app_context():
        write_audit(1, "existing", "older deployment")
        db = get_db()
        db.execute("DROP TRIGGER audit_log_no_update")
        db.execute("DROP TRIGGER audit_log_no_delete")
        db.commit()
    upgraded = create_app(dict(app.config))
    assert records(upgraded, "existing")[0]["details"] == "older deployment"
    with upgraded.app_context():
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            get_db().execute("DELETE FROM audit_log")


def test_details_are_bounded_and_control_characters_removed(app):
    with app.app_context():
        write_audit(None, "test", "a\n\t\x00\x7f\x85" + "b" * 1000)
    details = records(app, "test")[0]["details"]
    assert len(details) == 500
    assert details.startswith("a     b")


def test_oversized_request_rejection_has_no_body_content(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 100
    response = client.post("/login", data={"identity": "admin", "password": "SECRET" * 100})
    assert response.status_code == 413
    event = records(app, "request-rejected")[0]
    assert event["details"] == "method=POST; endpoint=login; status=413"


def test_unknown_login_is_shown_as_anonymous(app, client):
    client.post("/login", data={"identity": "unregistered", "password": "invalid"})
    authenticate(client)
    response = client.get("/admin/audit-log?event_type=login-failed")
    assert b"Anonymous / system" in response.data
    assert b"identity=unregistered" in response.data

@pytest.mark.parametrize(("value", "expected"), [
    (None, None), (42, None), ("", None), ("not-an-ip", None),
    ("1.2.3.4\n", None), ("x" * 46, None), ("fe80::1%eth0", None),
    ("198.51.100.4", "198.51.100.4"), ("2001:0db8::1", "2001:db8::1"),
])
def test_audit_peer_normalization(value, expected):
    from audit_address import normalize_audit_ip
    assert normalize_audit_ip(value) == expected


def test_http_audit_uses_direct_peer_not_forwarded_header(app, client):
    response = client.post(
        "/login", data={"identity": "admin", "password": "ChangeMe123!"},
        environ_overrides={"REMOTE_ADDR": "198.51.100.4"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert response.status_code == 302
    event = records(app, "login-success")[0]
    assert event["ip_address"] == "198.51.100.4"
    page = client.get("/admin/audit-log").get_data(as_text=True)
    assert "Peer IP" in page and "198.51.100.4" in page
    assert "203.0.113.9" not in page
    with app.app_context():
        write_audit(None, "offline-event", "no HTTP peer")
    assert records(app, "offline-event")[0]["ip_address"] is None


def test_stock_threshold_and_import_include_peer_address(app, client):
    import io
    authenticate(client)
    peer = {"REMOTE_ADDR": "2001:0db8::1"}
    assert client.post("/components/1/stock", data={"adjustment": "stock-in", "quantity": "1", "note": "test"}, environ_overrides=peer).status_code == 302
    assert client.post("/components/1/threshold", data={"reorder_level": "5"}, environ_overrides=peer).status_code == 302
    data = b"sku,name,description,category,supplier,quantity,reorder_level,unit_price\nIMPORT-IP,Test,Test,Microcontrollers,Maker Supplies,7,5,12.50\n"
    assert client.post("/components/import", data={"file": (io.BytesIO(data), "test.csv")}, environ_overrides=peer).status_code == 200
    for event in ("stock-adjustment", "threshold-updated", "component-imported", "inventory-imported"):
        assert records(app, event)[0]["ip_address"] == "2001:db8::1"
        assert records(app, event)[0]["user_id"] == 1


def test_legacy_audit_migration_preserves_events_and_triggers(tmp_path):
    from contextlib import closing
    from app import ROOT, init_db
    path = tmp_path / "legacy.sqlite"
    schema = (ROOT / "schema.sql").read_text(encoding="utf-8")
    assert "    ip_address TEXT,\n" in schema
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(schema.replace("    ip_address TEXT,\n", ""))
        db.execute("INSERT INTO audit_log (event_type, details) VALUES ('legacy', 'original')")
    application = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False, "SECRET_KEY": "test-migration", "DATABASE": str(path)})
    with application.app_context():
        init_db()
        db = get_db()
        row = db.execute("SELECT * FROM audit_log WHERE event_type='legacy'").fetchone()
        assert row["details"] == "original" and row["ip_address"] is None
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError, match="Audit records cannot"):
            db.execute("UPDATE audit_log SET details='forged' WHERE event_type='legacy'")
        db.rollback()
    client = application.test_client()
    client.post("/login", data={"identity": "unknown", "password": "invalid"}, environ_overrides={"REMOTE_ADDR": "192.0.2.5"})
    assert records(application, "login-failed")[0]["ip_address"] == "192.0.2.5"
