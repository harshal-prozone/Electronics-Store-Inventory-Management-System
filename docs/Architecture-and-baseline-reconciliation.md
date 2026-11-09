# Architecture and submitted-baseline reconciliation

Status: **unapproved deviation; not a replacement for the submitted SRS/SAD/STP**. Original documents remain unchanged. Source: `ESIMS-2026-G07_SRS_SAD_STP .pdf` (55 pages, SHA-256 `311729bf2d507b550ccc8005dd25785c7421f9c78c60dd1919e7babf57e6e81f`) and `Software Requirements Specification.pdf` (SHA-256 `d907d9bf37289aff82ed86952001b4a32393d1149d4f669eef0e3704ef2ee135`). The combined PDF labels its v1.0 STP as submitted for review; signatures/approval are not established by a printed name.

## Actual system

Browser → Flask/Jinja routes in `app.py` → `inventory_service.py`, `inventory_import.py` and `input_validation.py` → single SQLite database (`schema.sql`). Flask-WTF protects forms; Werkzeug hashes passwords; ReportLab builds PDFs; the dashboard uses server-rendered HTML/CSS rather than Chart.js. Sessions use Flask's signed cookie. SQLite `BEGIN IMMEDIATE` serializes the implemented stock changes; SQLite is not PostgreSQL row locking. Categories and suppliers are stored as names in component records, not foreign keys. `init_db()` creates schema and applies limited startup migrations; it is not a versioned migration framework. See `SETUP_AND_TESTING.md` for installation and backup guidance. GitHub Actions uses pytest, a setup smoke test, a loopback benchmark and Selenium's vendor-stable browser workflows.

## Material differences requiring an authorized decision

| Submitted SAD/STP baseline | Current implementation / evidence | Consequence and required action |
|---|---|---|
| Django 5, Django REST Framework, JSON endpoints | Flask form routes; no corresponding DRF API | Original API status codes, JSON schemas and Postman/DRF APIClient cases cannot be treated as passed; agree to migration or formally approve deviation. |
| PostgreSQL 14 and row locking | SQLite single-file database with write-lock serialization | Current concurrency tests support SQLite only; no PostgreSQL locking/deployment proof. |
| Bootstrap 5, Chart.js; category chart | Custom CSS and server-rendered availability chart | Not the specified framework/chart; assess design and original dashboard case. |
| Docker Compose, nginx, HTTPS, restart policies | No delivered Compose/nginx production deployment | TLS, redirect/HSTS, isolation, deployment monitoring and availability require an actual deployment. |
| Jenkins, Postman, Locust, SonarQube, Bandit, pip-audit, ZAP | GitHub Actions, pytest and Selenium; local scanner results in `Final-Engineering-Validation.md` | GitHub Actions is not Jenkins, Flask tests are not Postman, short loopback benchmark is not five-minute Locust; local scans are not configured per-build or an OWASP ZAP assessment. |
| Staff may create/edit components and generate reports (UC-02/03/08) | Current application restricts these actions to Admin | Material authorization difference, not an equivalent security implementation; obtain owner/course decision before changing access policy. |
| Account disable, five-failure lockout, supplier email, notifier | No corresponding mechanisms | Cases cannot pass as specified; implementation or explicit waiver required. |
| Django PBKDF2 hash format, idle timeout | Werkzeug default salted hashing, Flask permanent signed sessions | Salted hashing is supported, but exact format and specified idle/session behavior are not established equivalent. |
| One category/supplier references and in-use deletion rules | Stored text, application-level checks; no database foreign keys from components to catalogues | Application writes now use a serialized check/write sequence, but external writers bypass these checks; deleted-component reference semantics differ from baseline. |

Migration to the original stack would be a substantial new design and data migration, not a safe change inferred from a passing test suite. No authorized waiver has been supplied. An owner/faculty reviewer must either approve each deviation and acceptance basis or require implementation/migration and repeat applicable original cases. Preserve the original documents and record the dated decision and reviewer identity.

## Original requirement-to-implementation index

Labels below are summaries only; the PDF remains authoritative for exact text. “Related” means source/tests exist, not that every original requirement or STP case passed. Case IDs and per-case qualifications are in `Original-STP-reconciliation.md`. The original RTM remains in the PDF.

| Requirement | Actual implementation / related evidence | Principal qualification |
|---|---|---|
| FR-001 | `app.py` manage users; `tests/test_web_app.py` | Disable functionality absent from UC-10. |
| FR-002 | login route and authentication tests | Disabled accounts and lockout not implemented. |
| FR-003 | role decorators and authorization tests | Staff access differs from source use cases. |
| FR-004 | component creation and tests | Admin-only rather than authenticated Staff. |
| FR-005 | SQLite unique SKU, normalization and tests | SKU reserved after soft deletion. |
| FR-006 | component edit and tests | Admin-only; no DRF PATCH API. |
| FR-007 | soft-delete route and tests | No original DELETE API. |
| FR-008 | listing, query and pagination tests | Page size and HTTP interface differ from original API. |
| FR-009 | list filters and tests | DRF filter tests not executed. |
| FR-010 | `adjust_stock`; transaction tests | SQLite/form interface, not DRF. |
| FR-011 | `adjust_stock`; rollback/concurrency tests | SQLite only; no PostgreSQL evidence. |
| FR-012 | `availability_status`; service tests | Original notifier case not implemented. |
| FR-013 | category CRUD and tests | Catalogue references are text, not foreign keys. |
| FR-014 | supplier CRUD and tests | Supplier contact/email baseline missing. |
| FR-015 | report route and tests | Report restricted to Admin, contrary to UC-08 Staff. |
| FR-016 | CSV/PDF routes and tests | API/status expectations differ. |
| FR-017 | dashboard query and tests | Chart is availability rather than category. |
| FR-018 | `inventory_transactions`, service tests | Legacy and concurrent behavior need ongoing verification. |
| FR-019 | audit log and audit tests | Exact source fields/conditions, including IP, require case-level verification. |
| NFR-001 | `scripts/performance_test.py` | Local 100 requests only; original five-minute Locust case not run. |
| NFR-002 | readiness endpoints and sampler | One-week operational measurement outstanding. |
| NFR-003 | browser workflow and UAT record template | Independent representative user not established. |
| NFR-004 | SQLite transaction concurrency tests | PostgreSQL baseline not executed. |
| NFR-005 | service modules and tests | Business logic still exists in routes. |
| NFR-006 | local 5,000-item benchmark | Short loopback check, not original five-minute load. |
| NFR-007 | Selenium browser workflow | #83 passed; rerun required on changed revision. |
| NFR-008 | service functions tested independently | Not all business logic is in services. |
| SEC-001 | Werkzeug salted hashes and tests | Not original exact Django hash format. |
| SEC-002 | decorators, direct-access tests | Original API and access model not equivalent. |
| SEC-003 | validators, parameterized SQL and security tests | Scanner and manual penetration evidence incomplete. |
| SEC-004 | session and invalid-login tests | Lockout, disabled accounts and exact idle-timeout evidence absent. |
| SEC-005 | Flask-WTF CSRF and tests | Original API response and deployed HTTPS cross-origin case differ. |
| SEC-006 | `audit_log` and security-event tests | Full original actor/IP/event evidence requires further validation. |

Approval record: **not approved**. Reviewer, role, date, decision and evidence link: **not recorded**.
