# Sprint 2 demonstration run sheet

**Target duration:** approximately 2–3 minutes (confirm the course rubric).  
**Recording status:** this is a recording script, not a claim that a video exists.  
**Project:** Electronics Store Inventory Management System (ESIMS)

## Before recording

- Start the application using the documented setup in `docs/SETUP_AND_TESTING.md`.
- Use a prepared demo database with non-sensitive sample records.
- Sign in with a demo Admin account. Do not show real passwords, secret keys, personal data or `.env`.
- Keep one sample component ready with a known SKU, category, supplier, quantity and reorder threshold.
- Keep a valid CSV template and a deliberately invalid CSV row ready.
- Confirm that the app and database are healthy before recording.

## Recording sequence

| Time | Screen/action | Narration |
|---|---|---|
| 0:00–0:15 | Show application title and sign in as Admin | “This is ESIMS, a Flask and SQLite inventory management system for electronics components. It supports role-based access and auditable inventory operations.” |
| 0:15–0:40 | Open inventory; search/filter a component; open its details | “The inventory view supports search and filters. Component details show current stock and the configured reorder threshold, from which availability is classified.” |
| 0:40–1:05 | Show component transaction history; perform a small stock-in or stock-out on a demo record | “Stock movements are transactional and recorded in history with the resulting balance. Stock-out cannot reduce inventory below zero.” |
| 1:05–1:30 | Open CSV import; show template and import a small valid file; show result counts | “Admins can bulk import records. The importer validates the file, reports rejected rows and records quantity changes as adjustments.” |
| 1:30–1:50 | Show availability report and CSV/PDF export, or dashboard KPIs if that is the focus of the rubric | “The reporting views summarize inventory status and support export for operational review.” |
| 1:50–2:10 | Show audit log and `/health` endpoint | “Sensitive inventory actions are auditable, and the health endpoint reports application/database health. This endpoint is a diagnostic check; it is not itself proof of 99% operational uptime.” |
| 2:10–2:25 | Briefly show automated test result and setup guide | “This is the latest available automated test result for the revision shown. Setup and test instructions are documented for independent teammate verification.” |

## After recording

- Watch the complete recording once; confirm the text is readable and no credentials are visible.
- Save the final video in the team's approved location.
- Add the real URL, recording date, duration, presenter and reviewers to `docs/Sprint-2-deviations.md`.
- Do not write “demo completed” until the recording exists and the link has been checked.
