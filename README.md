# Electronics Store Inventory Management System (ESIMS)

A Flask + SQLite inventory management application for electronics components. Sprint 1 core functionality is merged into `main`; see the validation record for evidence and remaining manual closeout items.

## Implemented functionality

- Username/email authentication, Admin and Staff roles, password hashing, session expiry, and CSRF protection.
- Searchable, filtered and paginated component inventory.
- Admin-only component creation, editing, duplicate-SKU validation, and soft deletion.
- Admin-managed category and supplier catalogues, including validation, protected deletion, and association-preserving renames.
- Transactional stock-in/stock-out with transaction history; stock-out cannot exceed available quantity.
- Availability classification derived from quantity and reorder level.
- Admins can set or update each component's minimum stock threshold directly on its details page. Thresholds are non-negative whole numbers; positive stock at or below the threshold is Low Stock, and zero is Out of Stock. Changes immediately appear in inventory views and reports and are recorded in the audit log.
- Component CSV export and an Admin-only availability report with category, supplier, and status filters and CSV/PDF export.
- Admin-only bulk CSV import with SKU-based creation/updates, row error reports, imported/rejected counts, and audited stock adjustments.
- Audit entries for authentication and inventory-changing actions, a `/health` endpoint, and automated tests.
- Component transaction history with inclusive UTC date filters, transaction type filters, saved resulting balances, and pagination (20 per page), ordered newest first. History supports stock additions, removals, and adjustment records; the stock entry form records additions and removals.

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

flask --app app init-db
flask --app app create-admin
flask --app app run --debug
```

Open <http://127.0.0.1:5000>. The `create-admin` command prompts for a username, email, and password (minimum 10 characters). A normal installation does not create a known default administrator password. If `ADMIN_PASSWORD` is deliberately configured before first initialization, the app can seed an administrator from `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`; use a unique strong password and never commit it.

Set `SECRET_KEY` persistently. Development generates an ephemeral random key if one is absent, which invalidates sessions on restart. `APP_ENV=production` requires an explicit `SECRET_KEY`; set `COOKIE_SECURE=1` when served over HTTPS. Do not use Flask's development server for production.

For a fresh local database, point `DATABASE_PATH` to a new path before initializing. Existing administrator passwords are not changed by later environment-variable changes.

## Bulk inventory CSV import (Issue #19)

Sign in as an Admin, open **Inventory > Import CSV**, and download the header template. Upload a comma-separated UTF-8 CSV (a UTF-8 BOM is supported), up to 1 MiB and 5,000 nonblank records:

```csv
sku,name,description,category,supplier,quantity,reorder_level,unit_price
IMPORT-001,Example board,Imported component,Microcontrollers,Maker Supplies,10,5,19.50
```

All columns except `description` are required. Headers ignore case and surrounding spaces; `Reorder Level` and `Unit Price` are also accepted. The optional exported `Availability` column is ignored because availability is calculated from quantity and threshold. Category and supplier must already exist in their catalogues; names match case-insensitively and are stored with the catalogue's spelling.

The existing SKU rules apply: trim surrounding whitespace, normalize to uppercase, maximum 40 characters, start with a letter/number, and allow letters, numbers, dots, underscores, slashes and hyphens. A new SKU creates a component; an existing active SKU updates its details and **replaces its quantity with the supplied balance**, recording any stock change as an adjustment with the administrator and previous/resulting balances. Omitting `description` clears it. A deleted component's SKU remains reserved. Later occurrences of the same SKU within a file are rejected, including when the first occurrence has invalid field values.

Quantity and reorder level must be non-negative whole numbers within SQLite's signed 64-bit range; price must be finite and non-negative. Component names and text lengths follow the same validation as the component form. Empty lines are ignored. Incorrect field counts, invalid values, unknown catalogue entries and duplicate rows appear in the on-screen error report with their CSV line number and SKU; valid records still import. The result shows imported, created, updated and rejected counts. Correct and resubmit only rejected rows.

Invalid/missing/duplicate headers, unrecognized columns, encoding errors, malformed CSV quoting and file/record limits reject the whole file before writing. Database failures roll back the complete import, including history and audit records. Uploads use the existing Admin authorization and CSRF protection; the total HTTP request limit is 2 MiB to allow multipart overhead for a 1 MiB CSV.

## Automated tests

```bash
source .venv/bin/activate
pytest -q
git diff --check
```

The post-merge GitHub Actions run [40113760398](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/actions/runs/40113760398) passed **65 tests** and the Sprint 1 performance acceptance check. The closeout workflow adds clean-setup and Chrome/Edge/Firefox browser smoke jobs; use the actual pull-request checks as the evidence for those new jobs. A requirement-to-test map is in [`docs/Sprint-1-requirement-traceability.md`](docs/Sprint-1-requirement-traceability.md).

## Sprint 1 performance acceptance evidence

The current passing run tested a temporary SQLite database with 5,000 active components, 10 concurrent workers, and 100 listing/search/filter requests:

| Metric | Result |
|---|---:|
| Successful / failed requests | 100 / 0 |
| p50 response time | 54.93 ms |
| p95 response time | 194.24 ms |
| Maximum response time | 254.45 ms |
| Requests completed within 2 seconds | 100% |
| Acceptance threshold | At least 95% within 2 seconds |

This is a repeatable coursework acceptance test using a loopback threaded Flask server. It is not a production-network load test or proof of 99% operational availability.

## Troubleshooting

- If no administrator exists after initialization, run `flask --app app create-admin`.
- If imports fail, activate `.venv` and run `python -m pip install -r requirements.txt`.
- Back up the SQLite file before changing database paths or resetting a test database.
- The performance test uses its own temporary database and an ephemeral port.

## Data and integrity

The SQLite schema includes unique usernames, emails and SKUs, non-negative checks for quantities/reorder levels/prices, foreign-key relationships, transaction records, and audit events. Stock changes use `BEGIN IMMEDIATE` to protect transaction integrity.

SQLite is suitable for coursework and light single-instance use. The Sprint 1 benchmark passed the specified 5,000-component / 10-worker acceptance check, but this result does not demonstrate production availability or production-network capacity. Production use requires HTTPS, strong secrets, non-demo credentials, backups, monitoring, and an appropriate database strategy.

## Sprint 1 closeout status

The core Sprint 1 feature integration is merged. The latest automated verification passed 65 tests and the performance acceptance test. The remaining process evidence is tracked in [`docs/Sprint-1-validation.md`](docs/Sprint-1-validation.md), including the representative-user check, independent teammate verification of setup instructions, formal review, requirements traceability, and the separately-recorded demo video.

## Contributor workflow

Work on a feature branch, add tests for acceptance criteria, run the full suite and `git diff --check`, and submit a pull request to `main`. Close issues only when their acceptance evidence is linked and the issue's scope has been checked.


## Deployment health checks and availability (Issue #17)

The application exposes three unauthenticated health endpoints:

| Endpoint | Purpose | Healthy response |
|---|---|---|
| `/health/live` | Process liveness; does not depend on SQLite | HTTP 200 |
| `/health/ready` | Application and SQLite readiness | HTTP 200 |
| `/health` | Backward-compatible readiness endpoint | HTTP 200 |

Readiness returns HTTP 503 with `{"status":"error","database":"unavailable"}` when the SQLite query fails. A deployment should use `/health/live` for process liveness and `/health/ready` for readiness or traffic admission. Do not restart a process solely because its database is temporarily unavailable; use readiness to remove it from service while investigating the dependency.

For production deployment:
- Run behind a production WSGI server and HTTPS reverse proxy; do not use Flask's development server.
- Configure the platform's liveness probe to request `/health/live`.
- Configure its readiness probe to request `/health/ready`.
- Set probe timeouts and retry thresholds appropriate to the hosting platform.
- Keep `SECRET_KEY` persistent and secret; use non-demo credentials.
- Back up the database and monitor disk space, application errors, and database failures.
- SQLite is intended for coursework and light single-instance use. Evaluate a server database before multi-instance or higher-concurrency deployment.

### Measuring the 99% availability target

The SRS target is at least 99% availability during store operating hours, excluding planned maintenance. Automated tests and local performance benchmarks do not establish operational uptime.

Record probe results at a consistent interval throughout the agreed measurement period. Define store operating hours and the measurement period before collecting evidence. Exclude only documented planned-maintenance intervals.

Availability percentage:

`((eligible operating minutes - unplanned unavailable minutes) / eligible operating minutes) * 100`

The target is met when the measured result is at least 99%. Retain timestamped probe results, incident records, planned-maintenance records, and the calculation as evidence. Report the measurement period and actual result; do not claim compliance until sufficient observations exist.
