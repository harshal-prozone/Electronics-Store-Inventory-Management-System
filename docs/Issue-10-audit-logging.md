# Issue #10: audit logging and security-event recording

FR-019 and SEC-006 are implemented through persistent SQLite audit records and an
Admin-only, read-only review page at `/admin/audit-log` (Audit log in navigation).

## Recorded events

| Event | Details and attribution |
| --- | --- |
| `login-success`, `logout` | Authenticated account ID; username for successful login |
| `login-failed` | Attempted identity, bounded to 120 characters; anonymous actor because authentication failed |
| `authentication-required` | Anonymous attempt to use a protected endpoint |
| `access-denied` | Responsible account where available, HTTP method, endpoint and status 403 |
| `csrf-rejected` | Account resolved from the session where valid, method and endpoint; status 400 |
| `session-rejected` | Nonexistent or malformed session account; anonymous actor |
| `request-rejected` | Status 413/415, method and endpoint |
| `user-created` | Initiating Admin and new account ID/role; CLI-created accounts explicitly identify the CLI source and have no invented actor |
| `component-deleted` | Responsible Admin, component ID and SKU, retained after soft deletion |
| Other inventory/catalogue events | Existing creation, editing, catalogue deletion, threshold, stock and CSV import records are retained |

Every record has an increasing ID, event type, details, optional account foreign key,
a nullable direct network peer IP, and SQLite `CURRENT_TIMESTAMP` in UTC. Anonymous/system actions are labelled on the
review page. The page shows newest records first with ID as a deterministic tie
breaker, 25 records per page, event and account filters, and validated pagination.

The peer IP is the validated, canonical `request.remote_addr` supplied by the WSGI server, not an untrusted `X-Forwarded-For` header. Behind a reverse proxy it may identify the proxy rather than the originating client; configure trusted proxy handling separately and only for the known deployment topology. CLI/system events and invalid or unavailable peers are recorded as NULL. Existing rows remain NULL after the idempotent migration; no address is invented. IP addresses can be personal data: restrict access and establish a retention policy before deployment. No automatic purge is implemented.

## Integrity and access

- Login and Admin authorization are enforced on the review route. Staff and
  anonymous visitors cannot read audit contents; Staff have no navigation link.
- The review endpoint accepts GET only. No edit, deletion or public export route
  is provided, including for Admins. Responses use `Cache-Control: no-store`.
- Idempotent schema initialization installs indexes and triggers on existing
  databases without deleting history. Triggers reject UPDATE and DELETE of audit
  records, including foreign-key nullification if an attributed account is deleted.
  Accounts referenced by audit history must therefore be retained.
- Component soft deletion is locked and committed in the same transaction as its
  audit entry. Account creation and component/catalogue mutations likewise commit
  with their audit entries; an audit write failure rolls back pending changes.
  Stock adjustment and CSV import retain their existing atomic audit transactions.
- Successful login is audited before establishing the authenticated session.
  Audit storage failures propagate rather than silently losing a required event.
- SQL values are parameterized and templates escape user-supplied text. The app
  audit writer bounds details to 500 characters and replaces control characters.
  Security rejection details use application-owned endpoint names, not raw URLs,
  request bodies, query strings, passwords, password hashes or security tokens.
- These protections apply to application users and normal database writes. A
  database owner can change the schema or replace the file. Restrict filesystem
  access to `instance/`, the configured database and backups to the deployment
  account and authorized operators. Audit records are not a cryptographically
  signed or externally replicated security archive. No automatic retention purge
  is enabled.

## Validation

`tests/test_audit_logging.py` covers authentication events, UTC timestamps,
responsible users, anonymous/system display, CSRF before user loading, stale
sessions, access denials, oversized requests, safe details, atomic rollback,
append-only triggers, rejected web mutations, filters/pagination, XSS-safe rendering,
CLI account creation, direct peer attribution including stock/threshold/CSV events, spoofed forwarded-header rejection, IPv4/IPv6 validation, and upgrades preserving existing history and append-only triggers.

Run the backend suite in the project virtual environment:

```powershell
python -m pytest -q
```

`scripts/browser_compatibility.py` also exercises Admin audit review, event/user
filters, component deletion and Staff restrictions with CSRF enabled in stable
Chrome, Edge and Firefox. It captures audit screenshots at desktop and narrow
widths. Runtime results and screenshots are written to the configured evidence
directory, and CI retains browser evidence as artifacts.

Local execution on 2026-11-01:

- After merging latest main (`b6bcd4c`, including input validation): full backend
  suite **271 passed**, including **38 new audit tests** (324.55 s).
  The restricted Windows runner used `--basetemp=instance/pytest-issue10-merged1
  -p no:cacheprovider` to keep temporary files inside the workspace.
- Stable Chrome **156.0.8078.80**, Edge **156.0.4314.58** and Firefox **159.0**:
  all nine browser workflow groups passed with CSRF enabled, including XSS and
  audit review/deletion checks. Evidence: `instance/issue10-browser-evidence/<browser>/`.
- Desktop and narrow screenshots were inspected; the navigation wraps at narrow
  widths and the audit table uses the existing inventory table spacing.

For demonstration, sign in as Admin, delete an unused component, open Audit log,
and select `component-deleted` plus the responsible Admin. Capture the UTC
timestamp, account, SKU and ID. Also capture `login-failed` after an unsuccessful
login and the rejection when Staff opens `/admin/audit-log` directly.
