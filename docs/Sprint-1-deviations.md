# Sprint 1 deviations and verification gaps

**Sprint window:** 19-23 October 2026

This record captures deviations visible from GitHub history and the current repository. It should be reconciled against the submitted SRS, SAD and Test Plan before the final demonstration; it does not claim to replace that comparison.

| Item | Evidence | Explanation / follow-up |
|---|---|---|
| Availability-report delivery date | PR #31 merged on 24 October 2026; Sprint 1 ended 23 October. | Feature is now merged, but the recorded integration date is one day after the scheduled sprint. Explain the schedule deviation during the final demo. |
| Category/supplier management integration | PR #32 was open and non-mergeable at the time of audit, while Issue #8 had been closed. | Reopen Issue #8 and keep it open until conflict resolution, complete CI and merge. Do not claim the feature was delivered to `main` before that point. |
| Performance evidence for search/listing | Issue #7 requires at least 5,000 components, 10 concurrent users and 95% of requests within two seconds. No measured run was found in the existing repository record. | Run the supplied benchmark after applying the code changes; link the actual GitHub Actions run and report the measured p95/failure count. |
| PR review evidence | Automated workflows ran, but no formal submitted reviews were found for PRs #26, #27, #28, #29, #31 and #32 at audit time. | A real repository owner/team member must review the final PR(s). Do not treat the commit author or a green workflow as review evidence. |
| One-minute sprint demo | No video file was found in the repository file tree at audit time. | Record the working application and upload the actual one-minute video. The included demo script is only a recording plan. |
| Cross-browser/useability evidence | No completed browser matrix or representative-user result was found in the repository record. | If these are required by the submitted SRS/Test Plan, execute them on the supported browsers and preserve the result. |

## Scope note

No undocumented functional deviation from the SRS/SAD/Test Plan is asserted here because the full submitted design and test-plan contents have not been verified in this record. The team should compare them point by point before the final demo and append any additional discrepancy with a planned resolution.
