# Security scanner review — local Flask/SQLite implementation

The raw Bandit and pip-audit results are in `evidence/final-remediation-2026-11-09/`. They were collected locally on 9 November 2026 against code revision `1509f49` for the final Bandit/ZAP runs and `a6808a3` for the earlier scan; these are not a comprehensive authenticated scan, penetration test, deployment review or independent security sign-off. Scanner findings are retained, not suppressed.

## Follow-up: authenticated local scan and regression tests (9 November 2026)

On application source revision `fa12d9a637ad9675647591f9c7014cd3c11efc4c`, ZAP 2.17.0 quick-scanned a **disposable loopback Flask/Werkzeug/SQLite instance** with a synthetic Admin session injected by the ZAP request-header replacer. Server logs confirm successful protected inventory, reports and Admin audit-page requests. The baseline control returned 200 with the synthetic session and 302 without it. Credentials and session are test-only; no production system or real data was involved. Raw reports, logs and a bounded protected-path sample are in `evidence/verification-cleanup-2026-11-09/`.

- First scan: 0 high, 0 medium, 1 low (Werkzeug server version disclosure), 4 informational alert types. The potential-XSS hotspot alert identified eight instances in filter options. These are **not confirmed exploits**; the original report is retained. The filter options derive from server-side database values or fixed status choices and are rendered in autoescaped Jinja attributes. `tests/test_input_security.py` now includes targeted malicious quote/event-handler attribute tests for inventory, reports and audit filters. These tests do not prove the absence of all XSS.
- The informational “sensitive information in URL” instance matched `user_id=1` in the Admin audit filter, not a password. An account identifier in a URL can still appear in access logs and browser history; restrict access and use an appropriate log-retention policy. Session-management and user-agent-fuzzer informational notices also remain in the report. No scanner alert has been silently suppressed.
- A second scan put the cached Firefox and geckodriver on PATH. It reported 0 high, 0 medium, 1 low and 3 informational alert types; its log shows the DOM-XSS active rule completed with 12 messages and 0 alerts. It also reports an unavailable client-integration Firefox profile, potentially outdated add-ons, and skipped OAST-dependent Log4Shell and script scanners. The first scan skipped the DOM-XSS rule. A short quick scan and 12 DOM-rule messages are not exhaustive, and results can vary by crawl.
- The latest local Bandit scan of `app.py`, `input_validation.py`, `inventory_service.py`, `inventory_import.py` and `audit_address.py` reported the same eight medium B608 and two low findings described below (exit 1); pip-audit reported no known vulnerabilities in 16 resolved dependencies (exit 0). Findings require review, not automatic dismissal. The new targeted security module run passed 66 tests. This is not the original Django deployment, a production or independent penetration test, SonarQube evidence, or ST-SEC-03 completion.

## Bandit 1.9.4

Bandit returned exit status 1 with eight medium B608 findings and two low findings. Review of the flagged source (an engineering assessment, not independent approval):

| Finding | Review and remaining limits |
|---|---|
| `app.py` B608: audit log count and rows | SQL fragments are fixed application strings selected by conditions; user filter values and pagination are SQLite bound parameters. |
| `app.py` B608: component list count and rows | Predicates are fixed application strings; search, category, supplier, limit and offset values are bound parameters. |
| `app.py` B608: transaction history count and rows | Predicates are fixed application strings; component ID, date/type filters and pagination are bound parameters. |
| `app.py` B608: availability report query | Predicates are fixed application strings; category and supplier values are bound parameters; the status selects fixed predicates. |
| `inventory_import.py` B608 | The flagged string is an error message selecting the word `category` or `supplier`; it is not executed as SQL. |
| B406 | `xml.sax.saxutils.escape` is used to encode text supplied to ReportLab Paragraphs, not to parse untrusted XML. |
| B105 | The deterministic account password is used only when Flask `TESTING` is true. A normal installation does not seed a known password. Protect test configuration and do not deploy with `TESTING` enabled. |

The static review does not prove every input path is safe. The code should be reviewed again after query changes and deployed security configuration must be assessed separately. Security-sensitive behavior is also exercised by `tests/test_input_security.py`, `tests/test_account_controls.py`, and `tests/test_supplier_alerts.py`.

## Dependency audit

`pip-audit -r requirements.txt --format json` exited 0 and reported no known vulnerabilities in the 16 resolved application/test packages at the time of this scan. Unpinned ranges can resolve differently later; this does not cover every optional browser or load-testing dependency, operating-system package, or live environment. Re-run for the actual deployment lockfile/environment.

## OWASP ZAP

A local ZAP 2.17.0 quick scan against an isolated **unauthenticated** loopback Flask development server at revision `a6808a3` reported 0 high, 1 medium (CSP `style-src` unsafe-inline), 1 low (Werkzeug server version disclosure) and 2 informational alert types. Revision `1509f49` removed inline styles and the `unsafe-inline` style directive; a follow-up quick scan reported 0 high, 0 medium, 1 low (development server version disclosure), and 2 informational alert types. Both HTML reports and logs are retained. The low finding must be addressed in a real server/proxy deployment; it is not closed by the application change.

These earlier scans covered only unauthenticated pages, not signed-in inventory functions or the production architecture. ZAP warned its add-ons might be out of date and could not start Firefox for the DOM XSS active scanner; relevant warnings are retained in `zap-final-diagnostics.log`. Therefore, those earlier results do not establish absence of vulnerabilities or completion of original ST-SEC-03. See the follow-up above for the later limited authenticated scan. Browser XSS tests are additional evidence, not a substitute for the skipped scanner or penetration testing.

## Not yet established

SonarQube and authorized manual penetration testing have not been performed here. HTTPS/TLS, secure headers at a proxy, production secret handling, operating-system protections and backup recovery require an actual deployment review. A reviewer must decide acceptance of any outstanding findings and deviations; scanner output alone is not sign-off.
