PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Admin', 'Staff')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    session_version INTEGER NOT NULL DEFAULT 0 CHECK (session_version >= 0),
    failed_login_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_login_count >= 0),
    first_failed_login_at INTEGER,
    locked_until INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    supplier TEXT NOT NULL DEFAULT '',
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    reorder_level INTEGER NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
    unit_price REAL NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('stock-in', 'stock-out', 'adjustment')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    previous_quantity INTEGER NOT NULL CHECK (previous_quantity >= 0),
    new_quantity INTEGER NOT NULL CHECK (new_quantity >= 0),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_components_name ON components(name);
CREATE INDEX IF NOT EXISTS idx_components_category ON components(category);
CREATE INDEX IF NOT EXISTS idx_components_supplier ON components(supplier);
CREATE INDEX IF NOT EXISTS idx_transactions_component_date
    ON inventory_transactions(component_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_date ON audit_log(created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event_date ON audit_log(event_type, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user_date ON audit_log(user_id, created_at DESC, id DESC);

-- Application audit history is append-only, including for Admin accounts.
-- Database owners must still protect the database file and backups.
CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'Audit records cannot be modified');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'Audit records cannot be deleted');
END;
