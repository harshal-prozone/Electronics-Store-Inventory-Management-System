# Electronics Store Inventory Management System (ESIMS)

A small, runnable Flask + SQLite coursework application scaffold, with its first implementation focused on Sprint 1 Issue [#11 — Availability Classification and Low-Stock Alerts](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/11).

> **Scope note:** The repository initially contained specification PDFs but no application source. Flask + SQLite is therefore a pragmatic implementation baseline, not a claim that the original PDFs prescribed this stack. This version intentionally does not mark the other Sprint 1 issues as complete. Features such as full role administration, category/supplier CRUD, bulk CSV import, PDF reports, high-load benchmarking, and complete deployment monitoring remain for their own backlog items.

## Implemented in this starter

- Component catalogue with name/SKU search, category/supplier/status filters, and pagination.
- Admin-only create/edit forms for catalogue records.
- Availability classification recalculated from current quantity and reorder level:
  - `quantity == 0` → **Out of Stock**.
  - `quantity > 0 and quantity <= reorder_level` → **Low Stock**.
  - `quantity > reorder_level` → **In Stock**.
- Stock-in and stock-out operations; stock-out beyond available quantity is rejected.
- Stock adjustments are performed together with their movement and audit-log records inside a SQLite `BEGIN IMMEDIATE` transaction.
- User login using username or email; password hashes use Werkzeug's password hashing; Admin and Staff roles are represented in the schema.
- Parameterized SQL, server-side validation, Jinja auto-escaping, session-cookie settings, CSRF protection on forms, and a basic `/health` endpoint.
- CSV export of the component catalogue.
- Seed data designed to demonstrate all three statuses.
- Automated unit and Flask integration tests; GitHub Actions workflow runs `pytest` on pushes and pull requests.

## Run locally (macOS / Linux)

Python 3.10+ is recommended. From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

# Development-only settings. Use your own strong values outside local demos.
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export ADMIN_USERNAME="admin"
export ADMIN_EMAIL="admin@example.local"
export ADMIN_PASSWORD="ChangeMe123!"
export DATABASE_PATH="instance/inventory.db"

flask --app app run --debug
```

Open <http://127.0.0.1:5000>. The starter seeds an administrator account and demonstration components on first initialization. The demo credentials above are for local evaluation only; change them before using the app with real data. `SECRET_KEY` and `ADMIN_PASSWORD` are read when the database is first seeded; changing `ADMIN_PASSWORD` later does not automatically change an existing user's password.

To use a separate fresh database, set `DATABASE_PATH` to a new path and restart the application.

## Run tests

```bash
source .venv/bin/activate
pytest -q
```

Tests cover the status boundary rules, invalid negative/non-integer values, rendering of each availability state, stock-out status transitions, protection against negative stock, threshold edits, search input handling, and the health endpoint.

## Create an additional administrator

```bash
flask --app app create-admin
```

The CLI prompts for a username, email, and password. Passwords must be at least 10 characters.

## Data model

- `users` — username/email, password hash, and role.
- `components` — SKU, description, category, supplier, quantity, reorder threshold, and unit price.
- `inventory_transactions` — movement type, moved quantity, before/after quantity, user, note and timestamp.
- `audit_log` — selected security and inventory actions.

The `schema.sql` file sets non-negative constraints on quantity, reorder levels, and unit price, plus an index for recent per-component stock history.

## Important implementation notes

- Availability status is computed at read time from `quantity` and `reorder_level`, so it cannot become stale as stock changes.
- `BEGIN IMMEDIATE` serializes stock-changing transactions before they read the current quantity. The operation is rolled back if stock-out would take inventory below zero.
- SQLite is appropriate for local coursework and light single-instance use. The stated 5,000-component/10-user performance requirement still needs a repeatable load-test run before any performance claim is made.
- For a production deployment, set a strong secret, use non-demo credentials, enforce HTTPS (`COOKIE_SECURE=1`), restrict access, and select a database and backup strategy appropriate to the deployment.

## Git workflow for Issue #11

The intended feature branch is `feature/issue-11-availability-classification`. Put these source files in the checked-out repository while on that branch, review the diff, run the tests, and raise a pull request to `main`. Do not close Issue #11 until your team has run and reviewed the app and test suite.
