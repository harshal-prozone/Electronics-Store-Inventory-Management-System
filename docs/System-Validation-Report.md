# Sprint 2 System Validation Report

**Execution:** [GitHub Actions run #81](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/actions/runs/42583324982)
**Commit:** `39d64370c37ef3b8fb0f539a7d5da430fbcf4e11`
**Date:** 9 November 2026

## Environment
- Backend/setup: GitHub-hosted Ubuntu, Python 3.12.16.
- Browser matrix: Ubuntu 24.04, vendor-stable Chrome, Edge and Firefox.
- Isolated temporary SQLite databases; Flask and Selenium workflows.

## Results

| ID | Validation activity | Result |
|---|---|---|
| SV-01 | Backend unit/integration suite | PASS — 271 tests |
| SV-02 | Fresh database initialization | PASS |
| SV-03 | Administrator creation via CLI | PASS |
| SV-04 | Application startup and `/health` | PASS — HTTP 200, healthy DB |
| SV-05 | Stable Chrome workflow | PASS |
| SV-06 | Stable Edge workflow | PASS |
| SV-07 | Stable Firefox workflow | PASS |
| SV-08 | Performance: 5,000 components, 10 workers, 100 requests | PASS — 100 successful, 0 failed, p95 231.57 ms, 100% within 2 seconds |
| SV-09 | >=99% availability during store operating hours | NOT DEMONSTRATED; approved operating-hours definition and full measurement period required |
| SV-10 | Independent teammate fresh-clone verification | PENDING; owner/CI checks do not satisfy independent verification |
| SV-11 | Representative-user usability with complete metadata | PARTIAL; see `Issue-13-usability-compatibility.md` |

## Performance details
| Metric | Value |
|---|---:|
| Active components | 5,000 |
| Concurrent workers | 10 |
| HTTP requests | 100 |
| Successful / failed | 100 / 0 |
| p50 | 43.04 ms |
| p95 | 231.57 ms |
| Maximum | 267.11 ms |
| Within 2 seconds | 100% |
| Environment | Loopback Flask WSGI server with temporary SQLite |

This is a CI loopback performance test, not a production-network load test.

## Date-window qualification
The verifiable run #81 occurred on 9 November 2026. It cannot be represented as testing performed from 2–6 November. The available repository evidence does not establish a complete test campaign during that earlier window.
