# Issue #12: input validation and injection protection

SEC-003 is implemented through server validation, SQLite parameter binding, context-appropriate output escaping and a restrictive script policy. User text remains plain data: valid punctuation, Unicode and multiline descriptions/stock notes are preserved rather than stripping HTML-looking text or SQL keywords.

## Changes

- `input_validation.py` provides plain-text, account-field and bounded ASCII-integer validation for web requests and the administrator CLI.
- Component forms and CSV rows share validation in `inventory_service.py`. Quantities and thresholds must fit SQLite's signed 64-bit range; prices must be finite, non-negative decimal numbers. Numeric separators, superscript/Arabic digits and malformed numeric strings are rejected. Leading zeroes are normalized before conversion, so a long representation cannot trigger Python's integer-string limit.
- Stock movements validate both the requested quantity and the resulting balance before writing. Overflow, overselling, malformed quantities and oversized notes produce errors without changing stock, history or inventory audit records.
- Account creation validates username/email lengths, a usable email structure, the Admin/Staff role allowlist and 10–1024-character passwords. Password whitespace and Unicode are preserved; passwords are never echoed in validation feedback. Login input is bounded as well, and failed authentication has a generic response.
- Listing/report filters reject invalid statuses and oversized text rather than silently truncating or ignoring them. Pagination is bounded before calculating SQLite offsets. Out-of-range route identifiers return 404 instead of causing a SQLite binding overflow.
- Requests reject repeated scalar parameters, repeated file fields, unsupported control characters and unsupported POST formats. Existing CSRF and role checks remain enabled. Limits are 2 MiB per request, 128 KiB of form memory and 32 multipart parts; the existing CSV file/row limits still apply.
- The minimum Flask version is 3.1, where the form-memory and multipart-part limits are configurable through application settings.

## Safe database operations

All request-derived SQL **values** are supplied through SQLite `?` placeholders, including authentication, search, filters, component/catalogue/user changes, imported rows and stock notes. Dynamic `WHERE` fragments come from fixed application clauses and enums; user input is not used as an SQL identifier or concatenated into executable SQL. Schema initialization and migrations execute repository-owned SQL, not uploaded content.

The security suite submits authentication bypasses, `DROP TABLE` and `UNION SELECT` strings. It verifies that they cannot authenticate or change inventory through searches/filters. Free-text fields can store those strings literally through parameterized writes, with tables and other records intact.

## XSS handling

- Jinja autoescaping and quoted attributes encode user content in inventory, component details/edit forms, catalogue dropdowns, user management, stock history, validation feedback and CSV-import reports.
- PDF report text continues to use XML escaping before being passed to ReportLab. CSV exports continue to quote fields and prefix spreadsheet-formula cells; downloads retain explicit MIME types and attachment filenames.
- Every response sends `X-Content-Type-Options: nosniff` and a Content Security Policy permitting scripts only from this application. Inline scripts, inline event handlers, embedded objects and base-URL changes are blocked. The style/font policy preserves the existing inline dashboard styles and Google Fonts resources.
- Delete confirmation handlers moved from inline `onsubmit` attributes to `static/app.js`, loaded with `defer`. The browser tests verify that cancelling keeps the component and accepting submits its normal CSRF-protected deletion form.

No rich-HTML rendering or client-side insertion of untrusted HTML is introduced. The CSP supplements output escaping; it does not replace it.

## Error responses

| Status | Behavior |
|---|---|
| 400 | Malformed fields, invalid values, duplicate parameters, invalid filters, CSRF failures, or invalid CSV file structure. Forms show validation feedback; invalid stock/threshold operations render the component details with an error. |
| 401 | Incorrect username/email or password, without disclosing which credential failed. |
| 403 | An authenticated Staff user requests an Admin-only operation. |
| 404 | Missing/deleted components or out-of-range route identifiers. |
| 409 | A component SKU, catalogue name, username or email conflicts with an existing unique record. |
| 413 | Request/form upload limits are exceeded. |
| 415 | A form-only operation is sent an unsupported body type such as JSON. |

Valid form submissions keep their redirect-to-result behavior. A structurally valid CSV containing rejected rows still returns its normal batch report with imported/rejected counts; invalid rows do not write records. Tests that previously expected HTTP 200 for rejected forms were updated to require the appropriate 400/409 response while retaining their database assertions.

## Verification

On 1 November 2026, **63 security cases passed** as part of the complete **233-test** suite, which passed in 78.14 seconds. Coverage is in `tests/test_input_security.py`, supported by the existing CRUD, CSV, stock, integration and CSRF tests.

| Security area | Evidence |
|---|---|
| SQL injection | Authentication bypass attempts; malicious search/filter parameters; parameterized catalogue/component writes; database contents checked after rejected requests. |
| Stored XSS | Script/image/SVG/textarea payloads in component fields, catalogue names, account names, stock notes and CSV content. Parsed HTML must contain no injected executable nodes or event-handler attributes, and displayed text must remain literal. |
| Reflected XSS | Quote/attribute-breakout payloads in rejected SKU forms and inventory search, with exact decoded input values verified. CSV row-error reports remain inert. |
| Numeric and text validation | Unicode numeric glyphs, separators, exponents in whole-number fields, overflow, huge integers, null/control characters, invalid emails/roles, oversized passwords/notes and invalid filter values. |
| Integrity and compatibility | Service-level overflow checks, database rollback/no-write assertions, duplicate parameters, unsupported formats, CSRF protection, valid Unicode/punctuation/password whitespace and zero-padded numeric input. |
| Browser behavior | The Chrome/Edge/Firefox smoke includes actual stored/reflected XSS attempts, checks that no injected DOM or execution marker appears, and verifies cancel/accept delete confirmation under CSP. |

Local Chrome, Edge and Firefox Playwright smoke runs all passed on 1 November 2026, including the stored/reflected XSS checks and both delete-confirmation paths. After merging PR #44 from `main`, the same security checks are also included in the vendor-stable Selenium runner used by CI, `scripts/browser_compatibility.py`.

The synchronization with `main` at `d625ca6` was verified again: all 233 Python tests passed, and stable Chrome 156.0.8078.80, Edge 156.0.4314.58 and regular Firefox 159.0 passed all eight workflow groups, including the XSS and CSP-compatible delete-confirmation checks.

Performance acceptance passed with 5,000 components, 10 workers and 100 requests: 100 successes, no failures, p95 299.54 ms, and 100% within two seconds. This is a loopback coursework workload, not a production-network measurement.

Repeat the server/security checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_input_security.py
.\.venv\Scripts\python.exe -m pytest -q
```

Repeat the vendor-stable browser checks used by CI:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
$env:ESIMS_BROWSER='chrome' # repeat with edge and firefox
.\.venv\Scripts\python.exe scripts/browser_compatibility.py
```

The browser script uses a temporary database and test accounts, resolves current vendor stable versions and retains results/screenshots. The optional Playwright smoke remains available as `scripts/browser_acceptance.py`; its Firefox engine is patched. See the Issue #13 record for version-resolution and evidence details.

## References

- [Issue #12](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/12).
- [Flask security guidance: escaping, content types and CSP](https://flask.palletsprojects.com/en/stable/web-security/).
- [Python SQLite parameter placeholders](https://docs.python.org/3/library/sqlite3.html#how-to-use-placeholders-to-bind-values-in-sql-queries).
- [OWASP input validation guidance](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html).
