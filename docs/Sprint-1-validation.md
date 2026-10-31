# Sprint 1 validation record

**Scheduled sprint:** 19-23 October 2026

**Closeout audit:** 24 October 2026
**Scope source:** The Sprint 1 acceptance map in this repository covers Issues #5, #6, #7, #8, #9, #11 and #14. This record distinguishes code/CI evidence from human acceptance.

**31 October follow-up:** Issue #13 now has a participant-reported successful three-screen creation test and passing local vendor-stable Chrome, Edge and Firefox runs. See [`Issue-13-usability-compatibility.md`](Issue-13-usability-compatibility.md) for exact versions, execution records, scope and the current CI evidence mechanism. The closeout statements below describe the earlier 24 October audit.

## Latest merged-main automated verification

- GitHub Actions: [run 40113760398](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/actions/runs/40113760398)
- Result: **65 tests passed** on Python 3.12; the performance acceptance step passed.
- Performance inputs: 5,000 active components, 10 concurrent workers, 100 HTTP listing/search/filter requests.
- Results: 100 successful, 0 failed; p50 54.93 ms; p95 194.24 ms; max 254.45 ms; 100% completed within two seconds. Acceptance is at least 95% within two seconds.
- Environment qualification: temporary SQLite database and loopback threaded Flask WSGI server. This is a coursework acceptance test, not a production-network load test or proof of 99% availability.

## Sprint 1 issue acceptance map

| Issue | Requirement | Evidence and status |
|---|---|---|
| #5 | Authentication and user management | PR #26 merged; authentication, Admin/Staff access control, CSRF/session and user management tests are on `main`; Issue #5 has a manual acceptance report. |
| #6 | Component CRUD and SKU validation | PRs #28 and #30 merged; component creation/editing, duplicate SKU, validation, soft deletion, CSV exclusion and Staff restrictions are tested. |
| #7 | Search, filters and pagination | Search/filter/pagination regression tests and passing performance acceptance run 40113760398. Evidence meets the stated numeric threshold; reconcile the issue state and link the run. |
| #8 | Category and supplier management | PR #32 introduced the feature and PR #33 integrated it; the merged `main` test suite includes catalogue CRUD, authorization, protected deletion and association-preserving rename tests. |
| #9 | Stock-in/out and transaction history | PRs #27 and #29 merged; transaction records, rollback, failed stock-out and concurrent oversell behavior are tested; manual results are recorded on Issue #9. |
| #11 | Availability classification | Service boundary tests plus manual stock-in/out verification are recorded on Issue #11. This establishes status classification, not a separate email/SMS alert service. |
| #14 | Availability reports and CSV/PDF export | PR #31 merged; tests cover report filters, CSV/PDF response and Staff restrictions. Merge occurred on 24 October, after the scheduled 23 October sprint end. |

## Additional quality gates added by the closeout change

- **Clean setup smoke:** a fresh CI job installs `requirements.txt`, initializes a new database, creates an administrator, starts Flask and requests `/health`. Actual pass/fail is recorded by the pull-request workflow.
- **Cross-browser smoke:** a Playwright matrix exercises inventory search/filter/pagination, component creation in the three-view path (inventory → form → detail), stock adjustment/history, catalogue CRUD, filtered report CSV/PDF downloads, and Staff denial on Chrome, Edge and Firefox. Do not claim those browsers passed until every matrix job is green.
- Existing unit/integration tests remain the principal automated regression suite.

## Issue tracking reconciliation

- Issues #7 and #18 have objective passing evidence in run 40113760398. Close them only after linking the run and confirming the existing issue body is satisfied.
- Issue #22 largely duplicates the transaction rollback/concurrency criteria in Issue #9. The closeout script comments with the cross-reference and closes #22 as duplicate when authenticated GitHub CLI access is available; reopen it if the team identifies distinct requirements.
- Do not close #13 solely on the basis of automated browser smoke; the issue requires representative-user usability evidence in addition to browser compatibility.
- Issue #24 has setup instructions and a clean-run CI check; its explicit “another team member verifies the instructions” criterion requires a real teammate to follow them and record the result.

## Manual and team acceptance still required

- A teammate must review the closeout PR and submit a real GitHub review. No review submission was recorded on original PR #33.
- A representative user must complete the component-add workflow and record the usability result. The automated check verifies the three-view path but cannot attest to a person's experience.
- Compare the submitted SRS, SAD and Test Plan against the implementation line by line and update the traceability matrix. This record is currently grounded in GitHub issues/tests; it is not signed-off formal PDF traceability.
- The actual one-minute video remains a separate recording task and is intentionally outside the automated closeout changes; the storyboard is not the video.

## Schedule deviation

Availability reports (PR #31) and final Sprint 1 integration (PR #33) were merged on 24 October 2026, one calendar day after the recorded sprint end on 23 October. Keep this deviation visible in the final presentation.
