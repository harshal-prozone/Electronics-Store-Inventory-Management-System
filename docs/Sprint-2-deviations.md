# Sprint 2 deviations and development-freeze record

> Status: partially completed from repository issue records, validation documents, and the 8 November 2026 owner-run verification. Fields without evidence remain explicitly unrecorded. This is not a signed-off freeze or acceptance record.

## Sprint 2 plan

- Working sprint window recorded in project planning context: **26–30 October 2026**. The approved sprint-plan artifact/link was not located in the repository audit; confirm against the team's submitted plan before treating these dates as authoritative.
- Tracked Sprint 2 work items identified in repository history: Issues **#10, #12, #13, #15, #16, #17, #19, #20, #21, #23 and #24**. The exact approved scope baseline was not located; this list is the observed delivery/backlog set, not proof that every item was in the original commitment.
- Acceptance criteria source: the individual GitHub issue bodies linked in the delivery table below. A single approved Sprint 2 plan document was not found.

## Delivery summary

| Tracked item | Delivered result / evidence | Status |
|---|---|---|
| [Issue #10](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/10) — audit logging | Audit events, Admin-only read-only audit review, append-only safeguards and atomic audit transactions; `docs/Issue-10-audit-logging.md`, `tests/test_audit_logging.py`. Local validation recorded 38 audit tests within the 271-test suite on 1 November. | Issue closed; implementation evidence documented |
| [Issue #12](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/12) — input validation | Server-side validation, parameterized SQL, output escaping/CSP and security tests; `docs/Issue-12-input-validation.md`, `tests/test_input_security.py`. The issue record documents 63 security cases within a 233-test suite on 1 November. | Issue closed; implementation evidence documented |
| [Issue #13](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/13) — usability/browser compatibility | Selenium stable-browser workflow for Chrome, Edge and Firefox, with retained evidence; participant-reported three-screen Chrome task is recorded in `docs/Issue-13-usability-compatibility.md`. Participant name, exact session time/environment and screenshots were not supplied. | Issue reopened on 9 November 2026; participant evidence remains incomplete for an auditable usability sign-off |
| [Issue #15](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/15) — dashboard/KPI charts | Dashboard implementation and test evidence are recorded in repository history; issue is closed. | Issue closed |
| [Issue #16](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/16) — modular services/unit tests | Core service logic and automated tests are present, including `inventory_service.py` and `tests/test_inventory_service.py`. The issue is closed; retain the issue body as the acceptance source. | Issue closed |
| [Issue #17](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/17) — health checks/availability | `/health` endpoint and dependency status checks are implemented and tested. No defined operational measurement period or uptime evidence for the 99% target was found. | Issue reopened on 9 November 2026; 99% availability criterion is **not demonstrated** |
| [Issue #19](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/19) — CSV import | Bulk CSV import, validation/error reporting and duplicate-SKU handling are implemented; see `tests/test_csv_import.py` and README. | Issue closed |
| [Issue #20](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/20) — custom low-stock thresholds | Per-component reorder thresholds and availability classification are implemented; see application and service tests. | Issue closed |
| [Issue #21](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/21) — component transaction history | Component-level transaction history, date/type filters and resulting balances are documented and implemented. | Issue closed |
| [Issue #23](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/23) — integration testing | Inventory workflow integration tests cover persistence, stock movement, history and error/rollback scenarios; see `tests/test_inventory_workflow_integration.py`. | Issue closed |
| [Issue #24](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/24) — setup/testing documentation | Setup, database initialization, application startup, test execution and troubleshooting are documented in `docs/SETUP_AND_TESTING.md`. Owner-run fresh-clone test passed, but the issue explicitly requires another team member to verify the instructions. | **Reopened / partial** — independent teammate verification remains outstanding |

## Deviations and scope changes

| Date / period | Planned item | Observed deviation or qualification | Reason / decision owner | Impact |
|---|---|---|---|---|
| 26–30 October 2026 (working window; confirm approved plan) | Sprint 2 tracked issues | Issue #24 was previously closed and was reopened on 9 November 2026; its independent teammate verification criterion has not been met. | No independent verification record was found; no decision owner/deferment approval recorded. | Setup documentation is delivered, but Issue #24 acceptance is incomplete. |
| By 8 November 2026 | Issue #13 usability sign-off | The repository contains a participant-reported successful three-screen test, but participant/session metadata and screenshots were not supplied. | Participant report; formal evidence owner/approval not recorded. | Browser automation is documented; representative-user evidence remains limited. |
| By 8 November 2026 | Issue #17 availability target | Health checks exist, but no operational observation period demonstrating 99% availability was found. | No measurement period or availability decision record found. | Do not claim the 99% availability NFR was validated, and the issue was reopened on 9 November 2026. |

## Defects and known limitations

- No open application defect is asserted here without a linked reproduction record.
- **Availability evidence gap:** `/health` is a health-check endpoint, not proof of 99% uptime. A local diagnostic sampled 6 successful probes out of 6 over 30 seconds (100% sampled availability); this does not establish the required operating-period target. See [Issue #17](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/17).
- **Usability evidence gap:** Issue #13's participant report lacks a supplied participant name, exact session time/environment and screenshots. See `docs/Issue-13-usability-compatibility.md`.
- **Setup acceptance gap:** Issue #24 was reopened and remains incomplete pending an independent teammate fresh-clone verification.
- The earlier audit did not inspect the SRS/SAD/Test Plan PDFs present in the repository; `docs/Sprint-1-requirement-traceability.md` is issue-based and explicitly not a formal PDF sign-off.

## Development freeze

- Freeze date/time and timezone: **No explicit development-freeze decision or timestamp was found. Do not infer one from the commit date.**
- Latest documented branch/commit: `main` at [`0968b16`](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/commit/0968b16), a documentation closeout commit pushed on 8 November 2026. This is a repository state reference, **not evidence that the team formally declared a freeze**.
- Owner-run automated verification: on the fresh-clone checkout based on commit `38eec1d`, Python 3.12.16 and `Flask-WTF 1.3.0`, **271 tests passed in 32.43 seconds** on 8 November 2026. A subsequent local verification after the evidence-pack changes passed **271 tests in 44.28 seconds**. These are local test results, not a GitHub Actions result.
- Previously audited CI evidence: workflow run #75 was recorded as passing backend, clean-setup smoke, Chrome, Edge and Firefox jobs in the 8 November validation audit. The CI status for commit `0968b16` has not been independently confirmed. The exact run URL/ID for run #75 was not available in the material reviewed for this record.
- Manual validation completed: Issue #13 participant-reported three-screen task; local vendor-stable browser execution records in `docs/Issue-13-usability-compatibility.md`; issue-specific manual evidence linked from Issues #10–#12. These are not a substitute for the outstanding independent teammate verification.
- Outstanding work: independent teammate setup verification for Issue #24; complete auditable representative-user evidence for Issue #13 if required by the rubric; measure the 99% availability NFR if it remains an acceptance requirement; formal SRS/SAD/Test Plan traceability; actual demo recording; peer review/sign-off. No approved deferment rationale was found for these items.

## Demonstration

- Sprint 2 demo recording URL: **Not found in the repository audit.**
- Recording date: **Not recorded.**
- Duration: **Not recorded.** The prior project planning context called for an approximately two-minute Sprint 2 demonstration; confirm the course rubric and attach the actual recording.

## Sign-off

- Prepared by: **Not recorded in repository evidence.**
- Reviewed by: **No formal reviewer sign-off found.**
- Review date: **Not recorded.**


## Companion closeout artifacts

- [Sprint 2 acceptance traceability](Sprint-2-acceptance-traceability.md)
- [Sprint 2 demo run sheet](Sprint-2-demo-run-sheet.md)
- [Issue #17 availability measurement procedure](Sprint-2-availability-measurement.md) and `scripts/measure_availability.py`

These artifacts organize and prepare the remaining verification work. They do not claim that a demo was recorded, an independent teammate verification was performed, or the operational availability target was measured.
