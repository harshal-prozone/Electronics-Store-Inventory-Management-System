# Sprint 1 validation record

**Scheduled sprint:** 19-23 October 2026  
**Validation date:** 24 October 2026  
**Purpose:** Track actual evidence against the Sprint 1 backlog and the Software Engineering Mini-Project Deliverables Part-2 brief.

## Automated verification currently visible on `main`

- GitHub Actions: [run 40067291817](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/actions/runs/40067291817)
- Result: **53 tests passed** on Python 3.12 (current merged `main` revision at the time of audit).
- Existing test coverage includes authentication/roles, component CRUD and soft deletion, availability boundaries, transaction rollback/concurrency, reports and exports, CSV formula-injection handling, and key security configuration.
- This passing run does **not** validate the unmerged category/supplier branch or the performance benchmark until those changes are applied and CI runs again.

## Sprint 1 issue acceptance map

| Issue | Requirement | Current evidence / status |
|---|---|---|
| #5 | Authentication and user management | Merged PR #26; automated authentication/role/CSRF/session tests are on `main`. |
| #6 | Component CRUD and SKU validation | Merged PRs #28 and #30; CRUD, duplicate SKU, soft delete and Staff restrictions are tested. |
| #7 | Search, filters and pagination | Search, category/supplier/status filtering and pagination are implemented. Performance target was previously unverified; run `python scripts/performance_test.py` after applying the completion kit. |
| #8 | Category and supplier management | PR #32 contains the feature but is not merged and was marked non-mergeable at audit time. Keep Issue #8 open until integration and the combined test run succeed. |
| #9 | Stock-in/out and transaction history | Merged PRs #27 and #29; stock movement, rollback, concurrency and quantity traceability have automated coverage. |
| #11 | Availability classification | Service boundary tests and manual results are recorded on [Issue #11](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/11). |
| #14 | Availability reports and CSV/PDF export | Merged PR #31; filter/export tests and manual verification are recorded. Merge occurred 24 October, after the scheduled sprint ended on 23 October. |
| #22 | Transaction integrity/rollback | Functionality overlaps materially with Issue #9 and is covered in `inventory_service.py` plus rollback/concurrency tests. Close as duplicate only after confirming the team accepts #9 as the canonical ticket. |

## Performance acceptance procedure

Run the repeatable HTTP benchmark, preferably in the GitHub Actions workflow:

```bash
python scripts/performance_test.py
```

The script creates a disposable SQLite database, seeds at least 5,000 active components, starts a threaded loopback HTTP server, and issues 100 listing/search/filter requests using 10 concurrent workers. It prints the actual p50/p95/max latency, percentage within two seconds and failures. The pass condition is zero failed requests and at least 95% within two seconds.

**Evidence must be taken from the actual run log.** Do not enter an assumed latency result into this document. The benchmark is a repeatable coursework check, not a claim that a production deployment has been load-tested over its real network.

## Manual verification still required

- A repository owner/team member must review the relevant PR(s) and record a real GitHub review. Automated CI success is not a substitute for a review submission.
- A team member must record the one-minute working-product demo and upload the actual video to the repository. A script/storyboard is not the video.
- If the course requires cross-browser checks, capture actual Chrome, Edge and Firefox results instead of marking them complete by inference.
- Compare the implementation with the submitted SRS/SAD/Test Plan and update the deviation record below if those documents impose additional requirements.
