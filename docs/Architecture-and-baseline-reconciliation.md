# Architecture and submitted-baseline reconciliation

Status: **unapproved deviation; not a replacement for the submitted SRS/SAD/STP**. Original documents remain unchanged. Source: `ESIMS-2026-G07_SRS_SAD_STP .pdf` (55 pages, SHA-256 `311729bf2d507b550ccc8005dd25785c7421f9c78c60dd1919e7babf57e6e81f`) and `Software Requirements Specification.pdf` (SHA-256 `d907d9bf37289aff82ed86952001b4a32393d1149d4f669eef0e3704ef2ee135`). The combined PDF labels its v1.0 STP as submitted for review; signatures/approval are not established by a printed name.

## Actual system

Browser → Flask/Jinja routes in `app.py` → `inventory_service.py`, `inventory_import.py`, `input_validation.py` and `audit_address.py` → single SQLite database (`schema.sql`). Flask-WTF protects forms; Werkzeug hashes passwords; ReportLab builds PDFs; the dashboard uses server-rendered HTML/CSS availability and category charts rather than Chart.js. Sessions use Flask's signed cookie. SQLite `BEGIN IMMEDIATE` serializes the implemented stock changes; SQLite is not PostgreSQL row locking. Categories and suppliers are stored as names in component records, not foreign keys. `init_db()` creates schema and applies limited startup migrations; it is not a versioned migration framework. See `SETUP_AND_TESTING.md` for installation and backup guidance. GitHub Actions uses pytest, a setup smoke test, a loopback benchmark and Selenium's vendor-stable browser workflows.

## Material differences requiring an authorized decision

| Submitted SAD/STP baseline | Current implementation / evidence | Consequence and required action |
|---|---|---|
| Django 5, Django REST Framework, JSON endpoints | Flask form routes; no corresponding DRF API | Original API status codes, JSON schemas and Postman/DRF APIClient cases cannot be treated as passed; agree to migration or formally approve deviation. |
| PostgreSQL 14 and row locking | SQLite single-file database with write-lock serialization | Current concurrency tests support SQLite only; no PostgreSQL locking/deployment proof. |
| Bootstrap 5 and Chart.js | Custom CSS and server-rendered availability and stock-by-category charts | Not the specified UI frameworks; original dashboard case and design acceptance remain to be assessed. |
| Docker Compose, nginx, HTTPS, restart policies | No delivered Compose/nginx production deployment | TLS, redirect/HSTS, isolation, deployment monitoring and availability require an actual deployment. |
| Jenkins, Postman, Locust, SonarQube, Bandit, pip-audit, ZAP | GitHub Actions, pytest, Selenium and a local Locust runner; see `Security-Scanner-Review.md` | GitHub Actions is not Jenkins; Flask tests are not Postman; local loopback load is not the original deployed stack; local ZAP quick scans, including a synthetic Admin session, are not a complete deployment security assessment. |
| Staff may create/edit components and generate reports (UC-02/03/08) | Flask forms and reports allow both Staff and Admin; delete, bulk import and administration remain Admin-only. | Role discrepancy for these form workflows addressed; original DRF endpoints and formal case execution remain outstanding. |
| Account disable and five-failure lockout | Flask account status, session revocation and lockout are implemented; see `tests/test_account_controls.py` | Original DRF API/423 responses differ; formal case execution and approval remain. |
| Supplier email and notifier | Optional validated email and phone; durable in-app SQLite-triggered transition alerts | Related Flask/SQLite tests exist. There is no Django notifier or real email delivery; original cases and approach remain to be reviewed. |
| Django PBKDF2 hash format, idle timeout | Werkzeug default salted hashing, Flask permanent signed sessions with a simulated 30-minute idle-expiry test | Hash format differs; deployed HTTPS session behavior remains unverified. |
| One category/supplier references and in-use deletion rules | Stored text, application-level checks; no database foreign keys from components to catalogues | Application writes now use a serialized check/write sequence, but external writers bypass these checks; deleted-component reference semantics differ from baseline. |

Migration to the original stack would be a substantial new design and data migration, not a safe change inferred from a passing test suite. No authorized waiver has been supplied. An owner/faculty reviewer must either approve each deviation and acceptance basis or require implementation/migration and repeat applicable original cases. Preserve the original documents and record the dated decision and reviewer identity.

## Original requirement-to-implementation index

Labels below are summaries only; the PDF remains authoritative for exact text. “Related” means source/tests exist, not that every original requirement or STP case passed. Case IDs and per-case qualifications are in `Original-STP-reconciliation.md`. The original RTM remains in the PDF.

| Requirement | Actual implementation / related evidence | Principal qualification |
|---|---|---|
| FR-001 | `app.py` manage users and `tests/test_account_controls.py` | Flask form, not original API; original case execution remains. |
| FR-002 | login route and account-control tests | Disabled accounts and lockout implemented; original API and status codes differ. |
| FR-003 | role decorators and authorization tests | Form access now covers Staff create/edit/report; original API access rules still require implementation or approval. |
| FR-004 | component creation and tests | Staff and Admin can create through the Flask form; no original DRF API. |
| FR-005 | SQLite unique SKU, normalization and tests | SKU reserved after soft deletion. |
| FR-006 | component edit and tests | Staff and Admin can edit through the Flask form; no DRF PATCH API. |
| FR-007 | soft-delete route and tests | No original DELETE API. |
| FR-008 | listing, query and pagination tests | Page size and HTTP interface differ from original API. |
| FR-009 | list filters and tests | DRF filter tests not executed. |
| FR-010 | `adjust_stock`; transaction tests | SQLite/form interface, not DRF. |
| FR-011 | `adjust_stock`; rollback/concurrency tests | SQLite only; no PostgreSQL evidence. |
| FR-012 | `availability_status`; durable in-app transition alerts; `tests/test_supplier_alerts.py` | Not the original Django notifier; original integration case not independently executed. |
| FR-013 | category CRUD and tests | Catalogue references are text, not foreign keys. |
| FR-014 | supplier CRUD, optional contact fields, validation and tests | Not the original Django/DRF form or endpoint. |
| FR-015 | report route and tests | Staff and Admin can use the Flask report; no original DRF API. |
| FR-016 | CSV/PDF routes and tests | API/status expectations differ. |
| FR-017 | dashboard query and tests | Category-unit and availability charts use server-rendered progress bars; a current low-stock list and historical alerts are distinct. Not Chart.js; original case execution remains. |
| FR-018 | `inventory_transactions`, service tests | Legacy and concurrent behavior need ongoing verification. |
| FR-019 | audit log and audit tests | Direct validated peer IP is recorded for request events; behind a proxy it may be the proxy, and historical rows remain NULL. Original case-level execution remains. |
| NFR-001 | `scripts/performance_test.py` and `scripts/run_locust_benchmark.py` | See delivery validation for local execution; Flask/SQLite loopback is not the original deployed stack. |
| NFR-002 | readiness endpoints and sampler | One-week operational measurement outstanding. |
| NFR-003 | browser workflow and UAT record template | Independent representative user not established. |
| NFR-004 | SQLite transaction concurrency tests | PostgreSQL baseline not executed. |
| NFR-005 | service modules and tests | Business logic still exists in routes. |
| NFR-006 | local 5,000-item benchmark and Locust runner | Local synthetic workload only; see delivery validation. |
| NFR-007 | Selenium browser workflow | Run #94 passed on the earlier merged revision; repeat browser checks for any later revision. |
| NFR-008 | service functions tested independently | Not all business logic is in services. |
| SEC-001 | Werkzeug salted hashes and tests | Not original exact Django hash format. |
| SEC-002 | decorators, direct-access tests | Original API and access model not equivalent. |
| SEC-003 | validators, parameterized SQL and security tests | Scanner and manual penetration evidence incomplete. |
| SEC-004 | account-control tests cover lockout, account disabling and simulated 30-minute idle expiry | HTTPS deployment and original API/423 behavior remain unverified or different. |
| SEC-005 | Flask-WTF CSRF and tests | Original API response and deployed HTTPS cross-origin case differ. |
| SEC-006 | `audit_log` and security-event tests | Peer IP, actor, event and time are captured for request events; forwarded headers are not trusted. Original case execution and real deployment attribution remain unverified. |

Approval record: **not approved**. Reviewer, role, date, decision and evidence link: **not recorded**.
