# Sprint 2 remaining-evidence pack

This pack consolidates the remaining work identified in the live GitHub audit.

## Apply
Extract this ZIP into the repository root, allowing the `docs/` and `scripts/` folders to merge. Review the diff before committing.

## What this pack does
- Adds a consolidated closeout action register that records the latest audited commit and evidence state.
- Adds one consolidated closeout action register.
- Adds fill-in records for independent teammate setup verification, representative-user acceptance, and peer/mentor sign-off.
- Replaces the availability sampler with a corrected implementation that records actual start/end timestamps and evaluates a configurable sampled target.

## What it cannot truthfully complete for you
A human must still perform and attest to:
1. Another team member's clean-clone verification (Issue #24).
2. A real representative-user usability session and its metadata (Issue #13).
3. A real demo recording and provide its link.
4. A reviewer/mentor's actual review and sign-off.
5. An operational availability observation over the exact SRS-defined period and environment (Issue #17).

Do not fill these records with invented names, dates, screenshots, video URLs, uptime results, or approvals.

## Important tracker correction
Issue #17 is currently closed on GitHub even though its acceptance criteria explicitly require availability measurement over a defined period. The documents correctly retain this as **not demonstrated**. Reopen or amend the issue only if your team/project process requires the tracker to reflect the unmet criterion.

## Suggested final verification after applying
```bash
git diff --check
python -m pytest -q
git status
```
The test command should be run from the repository root with the project's virtual environment active.
