# Account security remediation and validation

Code and test revision: `e654c40` (9 November 2026). These are local engineering results, not a CI result or approval. Baseline PR run #84 applies to the earlier commit `8088be3`, not this revision.

## Implemented behavior

- An administrator can disable or re-enable another account from User Management. The server prevents self-disable; staff and anonymous users cannot change account status. CSRF protection applies.
- Disabling increments a per-user session version. Existing signed-cookie sessions become invalid, including if an old cookie is replayed after the account is re-enabled. Logging out revokes all sessions for that account, not just the current browser. Account status changes and audit records commit together.
- Five failed credential attempts for an existing active account within 15 minutes lock that account for 15 minutes. The counter is serialized in SQLite; a correct login after the lock expires resets it. Unknown or inactive accounts and locked accounts receive the same generic 401 failure response. Unlike the original Django/DRF specification, no JSON endpoint or 423 status is provided. Lockouts can be used to deny access to a known account; a production deployment needs additional rate-limiting/monitoring and an authorized recovery process. The application does not rate-limit unknown usernames.
- Permanent Flask sessions use a 30-minute sliding inactivity timeout. Signed cookies, the configured secret, the server clock and deployment settings remain relevant to security. Flask tests simulate elapsed time; a real HTTPS deployment observation is still outstanding.
- Startup migrations add fields to existing SQLite `users` tables. They preserve existing users and password hashes, and are tested for repeat initialization. Back up the database before upgrading, and test the upgrade on a copy. Existing legacy cookies without a session version are accepted as version 0 until their account is disabled or logged out.

## Executed verification

- Local full suite: `pytest -q --cov=app --cov=inventory_service --cov=inventory_import --cov-branch` → **295 passed, 0 failed**, 54.42 s, 243 warnings (including SQLite ResourceWarnings). This run used Linux and Python 3.13.15.
- `tests/test_account_controls.py` covers disable/re-enable, self-disable protection, staff/anonymous denial, CSRF, cookie replay after disable and logout, five failures, lock expiration, failure-window reset, concurrent failures, migration, idle expiry, and audit rollback. It does not claim original DRF cases have been executed.
- Measured coverage: **1,034/1,087 statements (95.12%)** and **282/312 branches (90.38%)**, restricted to `app.py`, `inventory_service.py`, and `inventory_import.py`. Raw JSON is retained under `evidence/account-security-2026-11-09/`.
- Clean local database initialization, documented administrator creation, repeat initialization and `/health/ready` succeeded; SQLite integrity check was `ok` and foreign-key check was empty. A teammate has not independently performed setup verification.
- Vendor-stable browser runner passed Chrome 157.0.8103.38, Edge 157.0.4341.42 and Firefox 159.0.1 on code revision `87f1451`; the later code revision adds only a test. Browser JSON results are retained. These are automated workflows, not a representative-user session; they do not exercise every new account-control UI action.
- Local loopback Flask/SQLite performance: 5,000 components, 10 threads, 100 requests, 100 successful, 0 failures, p95 488.93 ms, maximum 540.21 ms and 100% within two seconds. This is not the original five-minute Locust or production-network test.
- Bandit exited 1 with eight medium B608 and two low findings, retained as JSON; independent security review remains necessary. Earlier pip-audit found no known vulnerabilities in the resolved dependencies; this is not proof about other dependency resolutions or deployment. ZAP, SonarQube and authorized penetration testing remain outstanding.

## Outstanding

No PR CI run has yet tested these changes. The original Django/DRF/PostgreSQL architecture, supplier email, low-stock notifier, and other original-case execution/approval remain unresolved. The browser-based original acceptance and operational availability records still require real participants and a live environment. See `Architecture-and-baseline-reconciliation.md` and `Original-STP-reconciliation.md`.
