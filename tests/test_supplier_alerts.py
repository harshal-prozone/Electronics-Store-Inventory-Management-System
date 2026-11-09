import csv
import io
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app import create_app, get_db, init_db
from inventory_service import adjust_stock


@pytest.fixture
def app(tmp_path):
    return create_app({'TESTING': True, 'WTF_CSRF_ENABLED': False, 'SECRET_KEY': 'test',
                       'DATABASE': str(tmp_path / 'inventory.sqlite')})


@pytest.fixture
def client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
    return client


def test_supplier_contact_create_edit_validation_and_escaping(app, client):
    bad = client.post('/suppliers/new', data={'name': 'Bad', 'contact_email': 'robu@'})
    assert bad.status_code == 400
    with app.app_context():
        assert get_db().execute("SELECT count(*) FROM suppliers WHERE name='Bad'").fetchone()[0] == 0
    good = client.post('/suppliers/new', data={'name': '<Supplier>', 'contact_email': 'sales@example.org', 'phone': '+91 111'})
    assert good.status_code == 302
    with app.app_context():
        row = get_db().execute("SELECT * FROM suppliers WHERE name=?", ('<Supplier>',)).fetchone()
        supplier_id = row['id']
        assert (row['contact_email'], row['phone']) == ('sales@example.org', '+91 111')
    page = client.get('/suppliers').get_data(as_text=True)
    assert '&lt;Supplier&gt;' in page and '<Supplier>' not in page
    assert client.post(f'/suppliers/{supplier_id}/edit', data={'name': 'Updated', 'contact_email': 'bad@'}).status_code == 400
    assert client.post(f'/suppliers/{supplier_id}/edit', data={'name': 'Updated', 'contact_email': 'new@example.org', 'phone': '555'}).status_code == 302
    with app.app_context():
        row = get_db().execute('SELECT * FROM suppliers WHERE id=?', (supplier_id,)).fetchone()
        assert (row['name'], row['contact_email'], row['phone']) == ('Updated', 'new@example.org', '555')


def test_legacy_supplier_migration_and_repeat_init(tmp_path):
    path = tmp_path / 'legacy.sqlite'
    schema = Path('schema.sql').read_text().replace("    contact_email TEXT NOT NULL DEFAULT '',\n    phone TEXT NOT NULL DEFAULT '',\n", '')
    with sqlite3.connect(path) as db:
        db.executescript(schema)
        db.execute("INSERT INTO suppliers(name) VALUES ('Legacy')")
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'DATABASE': str(path)})
    with app.app_context():
        init_db()
        row = get_db().execute("SELECT name, contact_email, phone FROM suppliers WHERE name='Legacy'").fetchone()
        assert tuple(row) == ('Legacy', '', '')
        assert get_db().execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert get_db().execute('PRAGMA foreign_key_check').fetchall() == []


def test_stock_alert_transitions_and_transaction_rollback(app):
    with app.app_context():
        db = get_db()
        cid = db.execute("INSERT INTO components(sku,name,quantity,reorder_level) VALUES ('ALERT','Alarm board',7,5)").lastrowid
        db.commit()
        adjust_stock(db, component_id=cid, user_id=1, adjustment='stock-out', quantity=3)
        adjust_stock(db, component_id=cid, user_id=1, adjustment='stock-out', quantity=1)
        assert [tuple(r) for r in db.execute('SELECT status,quantity,reorder_level FROM stock_alerts WHERE component_id=?', (cid,))] == [('Low Stock', 4, 5)]
        adjust_stock(db, component_id=cid, user_id=1, adjustment='stock-out', quantity=3)
        adjust_stock(db, component_id=cid, user_id=1, adjustment='stock-in', quantity=2)
        assert [r[0] for r in db.execute('SELECT status FROM stock_alerts WHERE component_id=? ORDER BY id', (cid,))] == ['Low Stock', 'Out of Stock', 'Low Stock']
        db.execute('UPDATE components SET reorder_level=0 WHERE id=?', (cid,))
        db.execute('UPDATE components SET reorder_level=3 WHERE id=?', (cid,))
        db.commit()
        assert db.execute('SELECT COUNT(*) FROM stock_alerts WHERE component_id=?', (cid,)).fetchone()[0] == 4
        db.execute('CREATE TRIGGER fail_history BEFORE INSERT ON inventory_transactions BEGIN SELECT RAISE(ABORT, "forced failure"); END')
        db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            adjust_stock(db, component_id=cid, user_id=1, adjustment='stock-out', quantity=2)
        assert db.execute('SELECT quantity FROM components WHERE id=?', (cid,)).fetchone()[0] == 2
        assert db.execute('SELECT COUNT(*) FROM stock_alerts WHERE component_id=?', (cid,)).fetchone()[0] == 4


def test_alerts_from_csv_and_dashboard(client, app):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['sku','name','description','category','supplier','quantity','reorder_level','unit_price'])
    writer.writerow(['ALERT-CSV','<Alert board>','','Microcontrollers','Maker Supplies','2','5','1'])
    assert client.post('/components/import', data={'file': (io.BytesIO(output.getvalue().encode()), 'alerts.csv')}).status_code == 200
    page = client.get('/').get_data(as_text=True)
    title = page.split('<title>', 1)[1].split('</title>', 1)[0]
    assert 'Dashboard' in title and 'Recent stock alerts' not in title
    assert 'ALERT-CSV' in page and '&lt;Alert board&gt;' in page and '<Alert board>' not in page
    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM stock_alerts a JOIN components c ON c.id=a.component_id WHERE c.sku='ALERT-CSV' AND a.status='Low Stock'").fetchone()[0] == 1
    # Reimporting an unchanged status must not generate duplicate alerts.
    assert client.post('/components/import', data={'file': (io.BytesIO(output.getvalue().encode()), 'alerts.csv')}).status_code == 200
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM stock_alerts a JOIN components c ON c.id=a.component_id WHERE c.sku='ALERT-CSV'").fetchone()[0] == 1


def test_concurrent_stock_changes_record_one_entry_per_transition(app):
    with app.app_context():
        db=get_db()
        cid=db.execute("INSERT INTO components(sku,name,quantity,reorder_level) VALUES ('RACE-ALERT','Race',7,5)").lastrowid
        db.commit()
    def do_one(_):
        with app.app_context():
            return adjust_stock(get_db(), component_id=cid, user_id=1, adjustment='stock-out', quantity=2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(do_one, range(2)))
    assert sorted(results) == [(5,3), (7,5)]
    with app.app_context():
        assert [tuple(r) for r in get_db().execute('SELECT status,quantity FROM stock_alerts WHERE component_id=?', (cid,))] == [('Low Stock', 5)]
