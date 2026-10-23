# Electronics Store Inventory Management System (ESIMS)

A Flask + SQLite inventory management application for electronics components. The repository is developed against the linked functional and non-functional backlog; features should be considered complete only after their acceptance criteria, tests, and review are satisfied.

## Implemented functionality

- Username/email login, Admin and Staff roles, password hashing, session expiry, and CSRF protection.
- Searchable, filtered and paginated component inventory.
- Admin-only component creation, editing, duplicate-SKU validation, and soft deletion.
- Atomic stock-in/stock-out operations with transaction history; stock-out cannot reduce stock below zero.
- Availability classification derived from quantity and reorder level: zero is **Out of Stock**; positive quantity at or below the threshold is **Low Stock**; quantity above the threshold is **In Stock**.
- Component catalogue CSV export and an Admin-only availability report with category, supplier, and status filters and CSV/PDF export.
- Audit events for authentication and inventory-changing actions, a `/health` endpoint, and automated tests in GitHub Actions.

## Local setup (macOS/Linux)

Python 3.10+ is recommended. From the repository directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

export APP_ENV=development
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export DATABASE_PATH="instance/inventory.db"

# Initialize the database, then create a real administrator interactively.
flask --app app init-db
flask --app app create-admin
flask --app app run --debug
```

Open <http://127.0.0.1:5000>. No known default administrator password is created for a normal installation. The `create-admin` command prompts for a username, email, and password (minimum 10 characters). If `ADMIN_PASSWORD` is deliberately configured before the first initialization, the app can seed an administrator using `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`; use a unique strong password and do not commit it.

`SECRET_KEY` should be set persistently. Development will generate an ephemeral random key if one is absent, which invalidates sessions on restart. When `APP_ENV=production`, a configured `SECRET_KEY` is mandatory. Set `COOKIE_SECURE=1` when the app is served over HTTPS. Do not use Flask's development server for production deployments.

For a fresh local database, set `DATABASE_PATH` to a new path before initializing. Existing administrator passwords are not changed by later environment-variable changes; use the user-management workflow to create a new account or change credentials as appropriate.

## Run tests

```bash
source .venv/bin/activate
pytest -q
git diff --check
```

The tests cover availability boundary rules, component CRUD and input validation, authentication and role restrictions, stock transaction integrity/rollback/concurrency, report filters, exports, and CSV formula-injection handling. CI runs `pytest -q` on pushes and pull requests.

## Data and integrity

The SQLite schema includes unique usernames, emails and SKUs, non-negative checks for quantity/reorder levels/prices, foreign-key relationships, transaction records, and audit events. Stock changes are recorded transactionally with `BEGIN IMMEDIATE`.

SQLite is suitable for local coursework and light single-instance use. The requirement for at least 5,000 components and 10 concurrent users still requires a repeatable load-test run and documented response-time measurements before claiming the performance target is met. Production use also requires HTTPS, a strong secret, non-demo credentials, backups, deployment monitoring, and an appropriate database strategy.

## Contributor workflow

Work on a feature branch, add tests for the issue's acceptance criteria, run the full test suite and `git diff --check`, and submit a pull request to `main`. Keep issue closure tied to a merged and verified implementation rather than code presence alone.
