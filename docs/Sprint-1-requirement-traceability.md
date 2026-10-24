# Sprint 1 requirement traceability matrix

**Basis:** The GitHub issue bodies and merged source/tests were inspected on 24 October 2026. This matrix maps the issue-based acceptance requirements to implementation and test evidence. The submitted SRS/SAD/Test Plan PDFs still require a formal line-by-line team sign-off; this issue-based matrix must not be described as that sign-off.

| Requirement / acceptance area | Implementation evidence | Automated / manual evidence | Status |
|---|---|---|---|
| FR-001 user accounts | `app.py` Admin user management; unique username/email constraints in `schema.sql` | `test_admin_can_create_staff_user`, `test_duplicate_username_is_rejected`, `test_duplicate_email_is_rejected`; manual report on Issue #5 | Verified for Sprint 1 scope |
| FR-002 login | Username/email authentication and password hash verification in `app.py` | `test_login_accepts_email_address`, `test_inventory_requires_login`; manual report on Issue #5 | Verified |
| FR-003 / SEC-002 role enforcement | `login_required`, `admin_required`; Admin-only user/catalogue/component/report actions | Staff restriction tests for user management, component CRUD, catalogue management and availability report | Verified for covered actions |
| SEC-001 password storage | `generate_password_hash` / `check_password_hash`; no known normal-install default admin password | `test_non_testing_database_does_not_seed_a_known_default_password`; issue #5 manual evidence | Verified for covered setup/authentication behavior |
| SEC-004 session expiry | Permanent session configuration and login flow in `app.py` | `test_permanent_session_expires` | Verified |
| SEC-005 CSRF | Flask-WTF CSRF protection on state-changing forms | `test_login_post_requires_csrf_token`; form tokens in templates | Verified for tested routes |
| FR-004 component fields | `validate_component_form`, component create/edit views, SQLite constraints | `test_admin_can_create_component`, `test_admin_can_edit_component_details`, `test_component_creation_rejects_invalid_values` | Verified |
| FR-005 unique SKU | Unique SKU constraint and integrity-error handling | `test_duplicate_component_sku_is_rejected` | Verified |
| FR-006 edit component | Admin component edit route | `test_admin_can_edit_component_details`, `test_edit_cannot_change_quantity_without_transaction` | Verified |
| FR-007 soft deletion | `deleted_at` soft-delete field; active-list/export filtering | `test_soft_deleted_component_is_hidden_from_inventory_and_csv`, Staff restriction test | Verified |
| FR-008 searchable/paginated list | Parameterized search, deterministic sorting, bounded page size | `test_search_is_parameterized_and_handles_special_characters`, `test_inventory_pagination_and_filters_preserve_query_state` | Verified |
| FR-009 category/supplier/status filters | Component list query filters preserve query state | `test_inventory_pagination_and_filters_preserve_query_state`; performance workload includes combined filters | Verified for automated coverage |
| NFR-001 / NFR-006 response-time and load | `scripts/performance_test.py` uses a temp DB, 5,000 active components, 10 concurrent workers, 100 requests | [Merged-main run 40113760398](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/actions/runs/40113760398): 100/100 success, p95 194.24 ms, 100% within 2 seconds | Numeric coursework target passed; not a production-network result |
| FR-010 / FR-011 stock-in/out | `inventory_service.py::adjust_stock` with transactional quantity and movement updates | `tests/test_issue9_transactions.py`: stock-in, stock-out, rollback and concurrent oversell tests; manual Issue #9 report | Verified |
| FR-018 movement traceability | `inventory_transactions` records transaction type, quantity, prior/new quantities, note, user and timestamp | Issue #9 transaction tests and manual evidence | Verified for stored/recent history fields |
| NFR-004 concurrency safety | `BEGIN IMMEDIATE` stock adjustment transaction and non-negative database check | `test_concurrent_stock_out_cannot_overspend` | Verified by automated test |
| FR-012 availability classification | `inventory_service.py::availability_status` derives state from quantity/reorder level | `tests/test_inventory_service.py::test_availability_boundaries`; manual Issue #11 report | Verified; this does not imply an email/SMS alert service |
| FR-013 / FR-014 catalogue CRUD | Admin category/supplier routes, validation, protected deletion, transaction-based association-preserving rename | Catalogue tests in `tests/test_web_app.py`, including `test_renaming_catalogue_entry_updates_component_associations` | Verified |
| FR-015 / FR-016 availability report and exports | Admin-only report; category/supplier/status filters; CSV/PDF downloads | `test_availability_report_filters_by_category_supplier_and_status`, CSV/PDF export tests, Staff access test | Verified |
| SEC-003 input/injection protection | Server validation, parameterized SQL, Jinja autoescaping, CSRF, CSV formula escaping | Special-character search, invalid-value and formula-escaping tests | Partially verified; a full XSS/malicious-payload security suite remains tracked under Issue #12 |
| FR-019 audit logging | `audit_log` table and audit writes for login and inventory/catalogue mutations | Writes are present, but a dedicated audit browsing workflow was not found in the Sprint 1 acceptance map | Partially implemented; Issue #10 remains open |
| NFR-003 three-screen component creation | Visible route path is inventory → add-component form → component detail | Closeout Playwright test asserts the flow across Chrome/Edge/Firefox jobs | Automated screen-path check; a real representative-user test is still required for Issue #13 |
| NFR-007 supported browsers | Closeout workflow launches Chrome, Edge and Firefox and executes core UI flows | Actual matrix result must be green in the closeout PR before claiming browser acceptance | Pending until CI jobs execute and pass |
| NFR-002 99% operational availability | `/health` endpoint returns dependency status | Health route is unit-tested; no operational monitoring period or uptime measurements supplied | Not verified; Issue #17 remains open |
| NFR-005 / NFR-008 modular services | Core stock/availability logic in `inventory_service.py` and independently callable service functions | `tests/test_inventory_service.py` and transaction unit tests | Partially covered; Issue #16 remains open until its full criteria are reconciled |

## Non-functional and formal closeout qualifications

- The performance benchmark tests the stated loopback workload only; it does not establish production network latency, availability over store operating hours, or production database scalability.
- The browser matrix is automated compatibility evidence, not a substitute for an actual representative-user usability session.
- Setup CI confirms documented commands in a clean runner, but Issue #24 explicitly requires another team member to follow the instructions and record confirmation.
- Compare this matrix line by line with the exact submitted SRS, SAD and Test Plan PDFs. Additional requirements in those PDFs must be added rather than assumed satisfied by this issue-based map.
