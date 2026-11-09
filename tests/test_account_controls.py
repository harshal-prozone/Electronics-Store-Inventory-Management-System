"""Account lifecycle and session-revocation regression tests."""
import sqlite3

import pytest
from werkzeug.security import generate_password_hash

from app import ROOT, create_app


@pytest.fixture
def app(tmp_path):
    app = create_app({'TESTING': True, 'WTF_CSRF_ENABLED': False,
                      'SECRET_KEY': 'account-test-only', 'DATABASE': str(tmp_path / 'accounts.sqlite')})
    with sqlite3.connect(app.config['DATABASE']) as db:
        db.execute("INSERT INTO users (username,email,password_hash,role) VALUES (?,?,?,'Staff')",
                   ('staff1', 'staff1@example.invalid', generate_password_hash('StaffPass123!')))
    return app


def sign_in(client, username, password):
    return client.post('/login', data={'identity': username, 'password': password})


def user_id(app, name):
    with sqlite3.connect(app.config['DATABASE']) as db:
        return db.execute('SELECT id FROM users WHERE username=?', (name,)).fetchone()[0]


def test_disable_rejects_login_revokes_sessions_and_prevents_replay_after_enable(app):
    admin, staff = app.test_client(), app.test_client()
    assert sign_in(admin, 'admin', 'ChangeMe123!').status_code == 302
    assert sign_in(staff, 'staff1', 'StaffPass123!').status_code == 302
    cookie = staff.get_cookie('session').value
    uid = user_id(app, 'staff1')
    assert admin.post(f'/admin/users/{uid}/status', data={'action': 'disable'}).status_code == 302
    assert staff.get('/components').status_code == 302
    assert sign_in(staff, 'staff1', 'StaffPass123!').status_code == 401
    assert admin.post(f'/admin/users/{uid}/status', data={'action': 'enable'}).status_code == 302
    staff.set_cookie('session', cookie)
    assert staff.get('/components').status_code == 302
    assert sign_in(staff, 'staff1', 'StaffPass123!').status_code == 302
    assert staff.get('/components').status_code == 200
    with sqlite3.connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT is_active, session_version FROM users WHERE id=?', (uid,)).fetchone() == (1, 1)
        assert db.execute("SELECT event_type FROM audit_log WHERE event_type IN ('user-disabled','user-enabled') ORDER BY id").fetchall() == [('user-disabled',), ('user-enabled',)]


def test_self_disable_invalid_action_and_unknown_user_are_rejected(app):
    admin = app.test_client()
    assert sign_in(admin, 'admin', 'ChangeMe123!').status_code == 302
    admin_id = user_id(app, 'admin')
    assert admin.post(f'/admin/users/{admin_id}/status', data={'action': 'disable'}).status_code == 400
    assert admin.post(f'/admin/users/{admin_id}/status', data={'action': 'bogus'}).status_code == 400
    assert admin.post('/admin/users/999999/status', data={'action': 'disable'}).status_code == 404
    with sqlite3.connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT is_active, session_version FROM users WHERE id=?', (admin_id,)).fetchone() == (1, 0)


def test_staff_and_anonymous_cannot_change_user_status(app):
    staff, anonymous = app.test_client(), app.test_client()
    assert sign_in(staff, 'staff1', 'StaffPass123!').status_code == 302
    admin_id = user_id(app, 'admin')
    assert staff.post(f'/admin/users/{admin_id}/status', data={'action': 'disable'}).status_code == 403
    assert anonymous.post(f'/admin/users/{admin_id}/status', data={'action': 'disable'}).status_code == 302


def test_status_change_requires_csrf(app):
    app.config['WTF_CSRF_ENABLED'] = True
    client = app.test_client()
    with client.session_transaction() as state:
        state['user_id'] = user_id(app, 'admin')
    uid = user_id(app, 'staff1')
    assert client.post(f'/admin/users/{uid}/status', data={'action': 'disable'}).status_code == 400
    with sqlite3.connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT is_active FROM users WHERE id=?', (uid,)).fetchone()[0] == 1


def test_existing_user_database_migrates_without_resetting_accounts(tmp_path):
    path = tmp_path / 'legacy.sqlite'
    schema = (ROOT / 'schema.sql').read_text().replace(
        "    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),\n", ''
    ).replace("    session_version INTEGER NOT NULL DEFAULT 0 CHECK (session_version >= 0),\n", '').replace(
        "    failed_login_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_login_count >= 0),\n", ''
    ).replace("    first_failed_login_at INTEGER,\n", '').replace("    locked_until INTEGER,\n", '')
    password_hash = generate_password_hash('LegacyPass123!')
    with sqlite3.connect(path) as db:
        db.executescript(schema)
        db.execute("INSERT INTO users (username,email,password_hash,role) VALUES (?, ?, ?, 'Admin')",
                   ('legacy', 'legacy@example.invalid', password_hash))
    cfg = {'TESTING': True, 'WTF_CSRF_ENABLED': False, 'SECRET_KEY': 'legacy-test', 'DATABASE': str(path)}
    app = create_app(cfg)
    create_app(cfg)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT username,password_hash,is_active,session_version FROM users").fetchall() == [('legacy', password_hash, 1, 0)]
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    assert sign_in(app.test_client(), 'legacy', 'LegacyPass123!').status_code == 302


def test_five_failures_lock_account_then_expire_and_success_resets(app, monkeypatch):
    import app as app_module
    now = [1_000_000]
    monkeypatch.setattr(app_module.time, 'time', lambda: now[0])
    client = app.test_client()
    for _ in range(5):
        assert sign_in(client, 'staff1', 'wrong-password').status_code == 401
    # Correct credentials remain rejected during the lockout, including email alias.
    assert sign_in(client, 'staff1@example.invalid', 'StaffPass123!').status_code == 401
    with sqlite3.connect(app.config['DATABASE']) as db:
        assert db.execute("SELECT failed_login_count, locked_until FROM users WHERE username='staff1'").fetchone() == (5, now[0] + 900)
    now[0] += 900
    assert sign_in(client, 'staff1', 'StaffPass123!').status_code == 302
    with sqlite3.connect(app.config['DATABASE']) as db:
        assert db.execute("SELECT failed_login_count, first_failed_login_at, locked_until FROM users WHERE username='staff1'").fetchone() == (0, None, None)


def test_old_failures_do_not_accumulate_outside_window(app, monkeypatch):
    import app as app_module
    now = [1_000_000]
    monkeypatch.setattr(app_module.time, 'time', lambda: now[0])
    client = app.test_client()
    for _ in range(4):
        assert sign_in(client, 'staff1', 'wrong-password').status_code == 401
    now[0] += 900
    assert sign_in(client, 'staff1', 'wrong-password').status_code == 401
    with sqlite3.connect(app.config['DATABASE']) as db:
        assert db.execute("SELECT failed_login_count, locked_until FROM users WHERE username='staff1'").fetchone() == (1, None)
    assert sign_in(client, 'staff1', 'StaffPass123!').status_code == 302


def test_concurrent_failures_do_not_lose_lockout_updates(app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier = Barrier(5)
    def bad_login(_):
        client = app.test_client()
        barrier.wait(timeout=15)
        return sign_in(client, 'staff1', 'wrong-password').status_code
    with ThreadPoolExecutor(max_workers=5) as pool:
        assert list(pool.map(bad_login, range(5))) == [401] * 5
    with sqlite3.connect(app.config['DATABASE']) as db:
        count, until = db.execute("SELECT failed_login_count, locked_until FROM users WHERE username='staff1'").fetchone()
        assert count == 5 and until is not None
    assert sign_in(app.test_client(), 'staff1', 'StaffPass123!').status_code == 401


def test_logout_revokes_replayed_cookie_and_other_sessions(app):
    first, second = app.test_client(), app.test_client()
    assert sign_in(first, 'staff1', 'StaffPass123!').status_code == 302
    assert sign_in(second, 'staff1', 'StaffPass123!').status_code == 302
    saved_cookie = first.get_cookie('session').value
    assert first.post('/logout').status_code == 302
    assert second.get('/components').status_code == 302
    first.set_cookie('session', saved_cookie)
    assert first.get('/components').status_code == 302
    assert sign_in(first, 'staff1', 'StaffPass123!').status_code == 302
    assert first.get('/components').status_code == 200


def test_default_permanent_session_timeout_is_thirty_minutes(app):
    assert app.permanent_session_lifetime.total_seconds() == 1800


def test_failed_login_counter_rolls_back_when_audit_insert_fails(app):
    with sqlite3.connect(app.config['DATABASE']) as db:
        db.execute("""CREATE TRIGGER reject_failed_audit BEFORE INSERT ON audit_log
                      WHEN NEW.event_type='login-failed' BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END""")
    with pytest.raises(sqlite3.IntegrityError, match='audit unavailable'):
        sign_in(app.test_client(), 'staff1', 'wrong-password')
    with sqlite3.connect(app.config['DATABASE']) as db:
        assert db.execute("SELECT failed_login_count, first_failed_login_at, locked_until FROM users WHERE username='staff1'").fetchone() == (0, None, None)


def test_disable_rolls_back_when_audit_insert_fails(app):
    client = app.test_client()
    assert sign_in(client, 'admin', 'ChangeMe123!').status_code == 302
    uid = user_id(app, 'staff1')
    with sqlite3.connect(app.config['DATABASE']) as db:
        db.execute("""CREATE TRIGGER reject_disable_audit BEFORE INSERT ON audit_log
                      WHEN NEW.event_type='user-disabled' BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END""")
    with pytest.raises(sqlite3.IntegrityError, match='audit unavailable'):
        client.post(f'/admin/users/{uid}/status', data={'action': 'disable'})
    with sqlite3.connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT is_active, session_version FROM users WHERE id=?', (uid,)).fetchone() == (1, 0)
