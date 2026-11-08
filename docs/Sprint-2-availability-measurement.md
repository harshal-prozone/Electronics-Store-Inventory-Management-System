# Availability measurement procedure (Issue #17 / NFR-002)

## Purpose

Issue #17 requires at least 99% availability during store operating hours, excluding planned maintenance, measured over a defined period and evaluated against the SRS conditions. The `/health` endpoint is implemented, but a passing health-check unit test or one successful HTTP request does **not** demonstrate this non-functional requirement.

## Measurement protocol

1. Obtain the exact operating-hours definition, timezone, exclusions and minimum observation period from the approved SRS. Record them below before running the measurement.
2. Run the application in the environment that the SRS expects to evaluate. A localhost run is useful as a diagnostic exercise but must not be presented as production availability.
3. Run `python scripts/measure_availability.py --url http://127.0.0.1:5000/health --duration-seconds 3600 --interval-seconds 5 --csv availability-results.csv` for a one-hour diagnostic sample, or replace the duration with the approved SRS period.
4. Keep the CSV output, application logs, environment description, start/end timestamps and any planned-maintenance intervals.
5. Calculate availability using the SRS's prescribed method. The included script reports the proportion of successful probes; this is a sampled estimate, not continuous monitoring and not a replacement for the SRS definition.
6. Repeat over the required store operating hours if the SRS requires multiple days. Do not count planned maintenance as downtime only if the SRS explicitly excludes it.
7. Record the measured result and compare it to 99%. If the observation period or environment is insufficient, report “not demonstrated”.

## Measurement record (complete only after running)

- SRS reference / clause:
- Environment (host, OS, app server, database):
- Store operating-hours definition and timezone:
- Observation start (ISO 8601 with timezone):
- Observation end (ISO 8601 with timezone):
- Planned-maintenance intervals and source:
- Probe interval:
- Total probes:
- Successful probes:
- Failed probes:
- Sampled availability:
- SRS calculation method:
- Result against 99% target:
- Evidence file / logs:
- Run by / reviewed by:

## Interpretation warning

A one-hour sample at a five-second interval contains about 720 probes. A sampled success ratio can miss short failures between probes. For a formal operational NFR, use the monitoring/measurement method prescribed by the SRS and retain raw evidence. Do not extrapolate a short local test into a claim about long-term production uptime.
