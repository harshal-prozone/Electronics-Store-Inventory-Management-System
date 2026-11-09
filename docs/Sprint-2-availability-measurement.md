# Availability measurement procedure (Issue #17 / NFR-002)

## Requirement

Issue #17 states: at least 99% availability during store operating hours, excluding planned maintenance. It also requires measurement over a defined test period and evaluation against the SRS measurement conditions.

The `/health` endpoint, a passing health-check test, or one successful HTTP request does **not** demonstrate this requirement.

## Preconditions — obtain from the approved SRS

Record these before running a formal measurement:

- SRS clause / exact wording:
- Store operating hours:
- Timezone:
- Required observation period:
- Required deployment environment:
- Definition of successful availability:
- Planned-maintenance exclusion rules:
- Required calculation method:
- Responsible operator / reviewer:

If these are unavailable, a local sampler run is diagnostic only and the NFR remains **not demonstrated**.

## Diagnostic sampler

```bash
python scripts/measure_availability.py \
  --url http://127.0.0.1:5000/health \
  --duration-seconds 3600 \
  --interval-seconds 5 \
  --target-percent 99 \
  --csv availability-results.csv
```

This one-hour localhost sample is not a substitute for the approved operational period or environment.

## Evidence retention

Retain raw CSV, application/server logs, deployment description, start/end timestamps, monitoring configuration, planned-maintenance records, and reviewer sign-off. The sampler uses periodic probes and may miss outages between probes.

## Measurement record — fill only after the real run

- SRS reference / clause:
- Environment (host, OS, app server, database, deployment):
- Store operating-hours definition and timezone:
- Observation start (actual ISO 8601 with timezone):
- Observation end (actual ISO 8601 with timezone):
- Planned-maintenance intervals and source:
- Probe interval and timeout:
- Total probes:
- Successful probes:
- Failed probes:
- Sampled availability:
- SRS calculation method:
- Result against 99% target:
- Raw CSV and logs:
- Run by:
- Reviewed by:
- Limitations / deviations:

## Interpretation

The sampler's success ratio is an estimate from periodic probes, not continuous uptime. Do not extrapolate a short local run to a multi-day/month operational requirement. If the observation period or environment does not match the SRS, report **not demonstrated**.

## Tracker status

GitHub Issue #17 was reopened on 9 November 2026 because its body explicitly requires defined-period availability measurement; do not claim the criterion is met without a valid measurement.
