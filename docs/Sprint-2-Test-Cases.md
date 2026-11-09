# Sprint 2 Test Case Document (Updated)

**Repository baseline reviewed:** `main` at `39d64370` (9 Nov 2026)
**Latest verified execution:** [GitHub Actions run #81](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/actions/runs/42583324982)

> This is a repository-derived update mapped to current test modules and acceptance workflows. The original submitted Test Plan and Test Case Document were not found in the repository audit. Reconcile this document against those originals if they exist elsewhere. Run #81 is dated 9 November; it does not prove testing during 2–6 November.

## Test environment
- Backend/setup: GitHub-hosted Ubuntu, Python 3.12.16.
- Browser acceptance: Ubuntu 24.04, stable Chrome, Edge and Firefox.
- Isolated temporary SQLite databases; Flask test client/application; Selenium browser flows.
- Commands: `pytest -q`, `python scripts/performance_test.py`, clean setup smoke and `python scripts/browser_compatibility.py`.

## Updated test-case catalogue

| ID | Area | Scenario | Expected result | Evidence |
|---|---|---|---|---|
| TC-001 | Authentication | Valid credentials | Authenticated session | `tests/test_web_app.py` |
| TC-002 | Authentication | Invalid credentials | Login rejected | `tests/test_web_app.py` |
| TC-003 | Authorization | Staff requests Admin-only route | HTTP 403 / denied | `tests/test_web_app.py`, `tests/test_input_security.py` |
| TC-004 | CSRF/session | State-changing request with invalid CSRF token | Request rejected | `tests/test_web_app.py` |
| TC-005 | Component CRUD | Create component with valid unique SKU | Record saved and displayed | `tests/test_web_app.py`, browser runner |
| TC-006 | Component CRUD | Duplicate SKU | Validation error; no duplicate | `tests/test_web_app.py` |
| TC-007 | Component CRUD | Edit component | Updated fields persist | `tests/test_web_app.py`, browser runner |
| TC-008 | Component CRUD | Soft delete component | Removed from active inventory; history preserved | `tests/test_web_app.py` |
| TC-009 | Validation | Missing required / invalid numeric values | Validation error; no invalid persistence | `tests/test_web_app.py`, `tests/test_input_security.py` |
| TC-010 | Search | Search by name/SKU | Matching records returned | `tests/test_web_app.py`, browser runner |
| TC-011 | Filters | Combine category, supplier and status | Only matching records returned | `tests/test_web_app.py`, performance script |
| TC-012 | Pagination | Later and out-of-range page requests | Correct page behavior; no server error | `tests/test_web_app.py`, performance script |
| TC-013 | Stock | Stock-in movement | Quantity increases; movement persisted | `tests/test_issue9_transactions.py`, integration tests |
| TC-014 | Stock | Valid stock-out movement | Quantity decreases; movement persisted | `tests/test_issue9_transactions.py`, integration tests |
| TC-015 | Stock | Stock-out exceeds available quantity | Rejected; quantity unchanged | `tests/test_issue9_transactions.py`, browser runner |
| TC-016 | History | View transaction history | Correct movement, quantity, balance and ordering | transaction and integration tests |
| TC-017 | Availability | Quantity below/equal/above reorder threshold | Correct classification | `tests/test_inventory_service.py` |
| TC-018 | CSV import | Import valid CSV with new/existing SKUs | Create/update counts correct | `tests/test_csv_import.py`, browser runner |
| TC-019 | CSV import | Invalid rows / duplicate identifiers | Invalid rows rejected with row errors | `tests/test_csv_import.py` |
| TC-020 | CSV import | Download import template | Valid template response | `tests/test_web_app.py`, browser runner |
| TC-021 | Availability report | Filter by category/supplier/status | Report matches filters | `tests/test_web_app.py`, browser runner |
| TC-022 | Export | Export report as CSV | Non-empty valid CSV | `tests/test_web_app.py`, browser runner |
| TC-023 | Export | Export report as PDF | Non-empty valid PDF | `tests/test_web_app.py`, browser runner |
| TC-024 | Audit | Perform audited operation | Actor/action/time event recorded | `tests/test_audit_logging.py` |
| TC-025 | Audit | Modify/delete append-only audit record | Protected history unchanged / operation rejected | `tests/test_audit_logging.py` |
| TC-026 | Security | SQL injection/XSS-shaped input | Safely handled; no injection/execution | `tests/test_input_security.py` |
| TC-027 | Security | Malformed/untrusted request input | Validation and safe error response | `tests/test_input_security.py` |
| TC-028 | Integration | Inventory workflow through persistence/services | State remains consistent | `tests/test_inventory_workflow_integration.py` |
| TC-029 | Integration | Force failed transaction | Atomic rollback; no partial write | integration and transaction tests |
| TC-030 | Health | GET `/health` with healthy database | HTTP 200 and healthy status | health tests; CI setup smoke |
| TC-031 | Setup | Initialize clean DB and create admin via CLI | Schema and admin created | CI clean-setup smoke |
| TC-032 | Performance | 5,000 components, 10 workers, 100 requests | >=95% complete within 2 seconds | `scripts/performance_test.py` |
| TC-033 | Browser | Core workflow in stable Chrome | Pass; version/results retained | `scripts/browser_compatibility.py`, CI |
| TC-034 | Browser | Core workflow in stable Edge | Pass; version/results retained | `scripts/browser_compatibility.py`, CI |
| TC-035 | Browser | Core workflow in stable Firefox | Pass; version/results retained | `scripts/browser_compatibility.py`, CI |
| TC-036 | Responsive UI | Desktop/narrow viewport checks | No page-level horizontal overflow | browser runner screenshots/results |

## Latest execution summary
| Suite | Verified result |
|---|---|
| Backend unit/integration | 271 passed, 0 failed, 41.48 s (run #81) |
| Clean database/admin/health smoke | Passed (run #81) |
| Chrome stable | Passed (run #81) |
| Edge stable | Passed (run #81) |
| Firefox stable | Passed (run #81) |
| Performance | 100/100 successful; p95 231.57 ms; 100% within 2 s (run #81) |
| Line/code coverage | See `Code-Coverage-Report.md`, generated by coverage-enabled CI |
| Branch coverage | See `Branch-Coverage-Report.md`, generated by coverage-enabled CI |

## Qualifications
- Repository-derived catalogue; not a replacement for the unavailable original approved Test Plan.
- Latest verifiable full execution is 9 November 2026, not 2–6 November.
- 99% operating-hours availability is not established by a short health check.
- Independent teammate setup verification is separate from CI smoke testing.
- Representative-user evidence is in `Issue-13-usability-compatibility.md`.
