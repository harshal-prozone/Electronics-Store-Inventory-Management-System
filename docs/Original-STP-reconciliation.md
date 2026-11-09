# Original STP case reconciliation

> Preliminary engineering reconciliation, not an executed original-case result sheet or reviewer sign-off. The source is the submitted combined PDF (STP v1.0); original IDs and test expectations remain authoritative.

## Counting and method

Section 13.3 explicitly states 99 cases **including** cross-cutting security cases. It individually names 94 cases; Section 5.1 names five more (IT-SEC-01 and ST-SEC-02 through ST-SEC-05), giving 99 unique IDs. The proposal of 89 named cases and ten unnamed activities does not match the actual PDF. Section 5.1 additionally lists narrative security activities, which are not new numbered cases.

The table is a case-by-case *gap classification*, not a pass report: the baseline specifies Django services, DRF APIs and PostgreSQL; related Flask/SQLite tests are not automatically equivalent. No row is marked passed without executing the original steps and recording actual outcomes. A related path is a starting point for investigation, not proof it implements every assertion. See the source PDF for full prerequisites, data, steps and expected results.

Status key: **Related** = relevant implementation/tests exist but original case was not independently executed as specified; **Deviation** = required API, database or exact approach differs; **Missing** = the specified behavior is not implemented; **External** = required human or deployment evidence is not available.

| Original case | Scenario (short label) | Classification | Relevant current evidence / reason |
|---|---|---|---|
| UT-AUTH-01 | valid login | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-AUTH-02 | invalid password | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-AUTH-03 | Django PBKDF2-format salted password hashes | Deviation | Werkzeug salted password hashes, not Django PBKDF2-format hashes; tests/test_web_app.py |
| UT-AUTH-04 | disabled account rejected | Related | tests/test_account_controls.py; original Django service not executed |
| IT-AUTH-01 | DRF login API, JSON and role | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-AUTH-02 | idle expiry via API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-AUTH-03 | failed-login audit | Related | tests/test_web_app.py; tests/test_input_security.py |
| IT-AUTH-04 | five-failure account lockout | Deviation | tests/test_account_controls.py; Flask returns generic 401, not original DRF 423 |
| ST-AUTH-01 | role-based landing pages | Related | tests/test_web_app.py; tests/test_input_security.py |
| ST-AUTH-02 | blank login fields | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-01 | valid create | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-02 | duplicate SKU | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-03 | SKU normalization | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-04 | negative price | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-05 | negative reorder level | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-06 | mandatory fields | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-18 | initial availability | Related | tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-01 | staff creates and duplicates through API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-02 | stored XSS text | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| ST-INV-01 | staff adds component via UI | Related | Staff Flask form and three-screen browser flow: `tests/test_web_app.py`, `scripts/browser_compatibility.py`; not original-stack case execution. |
| UT-INV-07 | price and threshold edit | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-08 | threshold changes availability | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-09 | duplicate SKU on edit | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-10 | edit cannot change quantity | Related | tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-03 | staff edit via API and audit | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-04 | edit deleted component via API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-05 | invalid API data type | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| ST-INV-03 | edit via UI | Related | tests/test_web_app.py; tests/test_input_security.py |
| ST-INV-04 | cancel edit | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-11 | soft delete | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-12 | deleted items excluded | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-13 | history preserved on deletion | Related | tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-06 | admin deletion via API and audit | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-07 | staff deletion forbidden via API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-08 | unknown deletion via API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-09 | stock movement on deleted item via API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| ST-INV-05 | admin/staff deletion UI | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-14 | case-insensitive name search | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-15 | SKU search | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-16 | category filter | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-INV-17 | status filter | Related | tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-10 | combined API filters | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-11 | API pagination, page size 25 | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-12 | SQL injection search | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-INV-13 | invalid API filter | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| ST-INV-02 | list, filters and badges | Related | tests/test_web_app.py; tests/test_input_security.py |
| PERF-01 | five-minute ten-user Locust load | Deviation | `scripts/run_locust_benchmark.py` targets Flask/SQLite loopback, not the original deployed architecture; see delivery validation |
| UT-STK-01 | reject excess stock-out | Related | tests/test_issue9_transactions.py; tests/test_inventory_workflow_integration.py |
| UT-STK-02 | availability boundaries | Related | tests/test_issue9_transactions.py; tests/test_inventory_workflow_integration.py |
| UT-STK-03 | stock-in transaction | Related | tests/test_issue9_transactions.py; tests/test_inventory_workflow_integration.py |
| UT-STK-04 | reject nonpositive movement | Related | tests/test_issue9_transactions.py; tests/test_inventory_workflow_integration.py |
| UT-STK-05 | stock-out to zero | Related | tests/test_issue9_transactions.py; tests/test_inventory_workflow_integration.py |
| IT-STK-01 | stock-out API and history | Deviation | DRF endpoint absent; related Flask form tests: tests/test_issue9_transactions.py; tests/test_inventory_workflow_integration.py |
| IT-STK-02 | concurrent PostgreSQL stock-outs | Deviation | tests/test_issue9_transactions.py uses SQLite locks, not PostgreSQL row locks |
| IT-STK-03 | rollback on failure | Related | tests/test_issue9_transactions.py; tests/test_inventory_workflow_integration.py |
| IT-STK-04 | low-stock notifier transition | Related | Durable SQLite-triggered in-app alerts and `tests/test_supplier_alerts.py`; not the original Django mocked notifier execution |
| ST-STK-01 | stock-out UI | Related | tests/test_issue9_transactions.py; tests/test_inventory_workflow_integration.py |
| UT-CAT-01 | category case-insensitive uniqueness | Related | tests/test_web_app.py |
| UT-CAT-02 | delete unused category | Related | tests/test_web_app.py |
| UT-CAT-03 | protect in-use category | Related | tests/test_web_app.py |
| UT-SUP-01 | supplier email validation | Related | Optional contact email rejects `robu@`; `tests/test_supplier_alerts.py`; not original Django unit execution |
| UT-SUP-02 | protect in-use supplier | Related | tests/test_web_app.py |
| IT-CAT-01 | staff cannot create category via API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py |
| IT-CAT-02 | category rename via API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py |
| IT-CAT-03 | delete in-use category via API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py |
| ST-CAT-01 | manage catalogues via UI | Related | tests/test_web_app.py |
| UT-RPT-01 | status-filtered report | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-RPT-02 | report excludes deleted items | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-RPT-03 | CSV header and rows | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-RPT-04 | CSV formula injection | Related | tests/test_web_app.py; tests/test_input_security.py |
| IT-RPT-01 | filtered report API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-RPT-02 | PDF export API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| IT-RPT-03 | unsupported export format API | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| ST-RPT-01 | staff report and export | Related | Staff Flask report filters and CSV/PDF export: `tests/test_web_app.py`, `scripts/browser_compatibility.py`; not original-stack case execution. |
| UT-DSH-01 | active component count | Related | tests/test_web_app.py |
| UT-DSH-02 | stock-value calculation | Related | tests/test_web_app.py |
| UT-DSH-03 | low/out counts | Related | tests/test_web_app.py |
| UT-DSH-04 | empty dashboard | Related | tests/test_web_app.py |
| IT-DSH-01 | dashboard summary API and RBAC | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py |
| IT-DSH-02 | KPI changes after stock movement | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py |
| ST-DSH-01 | dashboard UI and category chart | Deviation | dashboard chart is by availability, not category; tests/test_web_app.py |
| ST-DSH-02 | dashboard load time, 5,000 items | Related | scripts/performance_test.py measures inventory list/search, not dashboard |
| UT-USR-01 | create staff account | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-USR-02 | duplicate username/email | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-USR-03 | weak password rejection | Related | tests/test_web_app.py; tests/test_input_security.py |
| UT-USR-04 | disable account and invalidate sessions | Related | tests/test_account_controls.py; original service/API case not executed |
| UT-USR-05 | prevent self-disable | Related | tests/test_account_controls.py; original service/API case not executed |
| IT-USR-01 | staff user-creation API denied | Deviation | DRF endpoint absent; related Flask form tests: tests/test_web_app.py; tests/test_input_security.py |
| ST-SEC-01 | staff opens admin URL | Related | tests/test_audit_logging.py; tests/test_input_security.py |
| ST-USR-01 | create staff then log in | Related | tests/test_web_app.py; tests/test_input_security.py |
| ST-NFR-01 | three-browser system flows | Related | run #83 stable browser jobs passed; not all original cases performed as specified |
| ST-NFR-02 | new-user usability walkthrough | External | representative-user walkthrough not established |
| ST-NFR-03 | one-week five-minute uptime probes | External | one-week operational observation not recorded |
| ST-NFR-04 | service coverage and no business rules in views | Deviation | business logic remains in views; coverage scope excludes portions of application |
| IT-SEC-01 | API POST missing CSRF token | Deviation | DRF endpoint absent; related Flask form tests: tests/test_audit_logging.py; tests/test_input_security.py |
| ST-SEC-02 | cross-origin POST | Related | tests/test_input_security.py; HTTPS/origin deployment conditions not established |
| ST-SEC-03 | Bandit, pip-audit and ZAP scans | Deviation | Local Bandit/pip-audit and unauthenticated ZAP quick scan only; DOM XSS scanner skipped, no authenticated scan, SonarQube or pipeline scans evidenced; see `Security-Scanner-Review.md` |
| ST-SEC-04 | security audit trail review | Related | tests/test_audit_logging.py; tests/test_input_security.py |
| ST-SEC-05 | HTTPS cookie flags and 31-minute idle timeout | External | simulated 30-minute expiry covered in tests/test_account_controls.py; deployed HTTPS observation not recorded |

## Exit criteria

Original execution results, high-priority pass rate, RTM approval, high-severity defect/security disposition, required scanners, original PostgreSQL concurrency, original-stack Locust execution, representative-user UAT and operating-hours availability are not established. The original STP exit criteria cannot be claimed met.
