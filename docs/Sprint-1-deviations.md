# Sprint 1 deviations and verification gaps

**Sprint window:** 19-23 October 2026

**Audit updated:** 24 October 2026

This record separates known schedule deviations, verified test evidence and human acceptance gaps. It is based on repository history and GitHub issue criteria; compare it with the submitted SRS, SAD and Test Plan before signing off formal traceability.

| Item | Evidence | Resolution / remaining action |
|---|---|---|
| Availability-report delivery date | PR #31 merged on 24 October; Sprint 1 ended 23 October. | Feature is merged and tested, but delivery was one day late. State the schedule deviation accurately in the demo. |
| Category/supplier integration | PR #32 merged 24 October; integration and association-preserving rename fix are in PR #33. | Resolved in `main`; the latest merged-main workflow passed 65 tests. Old statements that PR #32 is unmerged are obsolete. |
| Search/listing performance | Run 40113760398 tested 5,000 active components, 10 concurrent workers and 100 requests. | Passed: 100 successes, zero failures, p95 194.24 ms and 100% within two seconds. Do not infer production-network performance from this loopback test. |
| Issue #7 / #18 tracking | Performance feature and workload are implemented and covered by the passing CI run. | Attach the run to both relevant tickets and close only the criteria that are satisfied; keep any broader future work separately scoped. |
| Transaction integrity overlap | Issue #9 has rollback and concurrent stock-out regression tests; Issue #22 describes substantially the same criteria. | Treat #9 as canonical and close #22 as duplicate only with an explicit cross-reference and team agreement. |
| Formal PR review | No submitted formal review was found for original PR #33. | Request a teammate review on this closeout PR; do not backdate or claim a review that did not occur. |
| Cross-browser compatibility | New Playwright CI jobs exercise Chrome, Edge and Firefox in the closeout change. | Await green browser-matrix results, then link the actual run. A representative-user usability session is still needed for Issue #13. |
| Setup documentation | README lists prerequisites, venv, dependency installation, environment, database initialization, admin creation, run and test commands. | A clean-setup CI smoke job is added. Issue #24 still needs another team member to follow the instructions and record independent confirmation. |
| SRS/SAD/Test Plan traceability | Issue-based traceability and automated tests are recorded here; no signed-off, full line-by-line comparison is available in this evidence set. | Team must compare the submitted PDFs to the live implementation and document any additional deviations before declaring formal traceability complete. |
| One-minute product demo | A storyboard exists, but it is not a recorded video. | Recording is intentionally excluded from this closeout change; do not claim the video evidence exists. |

## Scope qualification

This file does not claim that unrelated backlog items (such as bulk import, a KPI dashboard, 99% operational availability, full audit-log browsing, or date-filtered transaction-history browsing) were delivered merely because adjacent capabilities exist. See `PROJECT_NOTES.md` and the corresponding open GitHub issues for their actual acceptance status.
