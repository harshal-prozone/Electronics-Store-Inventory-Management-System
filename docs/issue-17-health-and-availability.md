# Issue #17 — Health checks and availability evidence

## Health endpoints

- `GET /health/live`: process liveness. Returns HTTP 200 while the Flask application can serve the request. It deliberately does not query SQLite.
- `GET /health/ready`: readiness. Executes `SELECT 1` against SQLite. Returns HTTP 200 when the query succeeds and HTTP 503 when SQLite raises an error.
- `GET /health`: backward-compatible alias for readiness.

These endpoints bypass session-user loading so that health probes do not require authentication or an additional database query before the check.

## Deployment configuration

Configure the hosting platform or reverse proxy as follows:

| Probe | Path | Expected success |
|---|---|---|
| Liveness | `/health/live` | HTTP 200 |
| Readiness | `/health/ready` | HTTP 200 |

Use a production WSGI server, HTTPS, persistent secrets, non-demo credentials, database backups, and monitoring. Use readiness failures to stop routing traffic to an instance whose database dependency is unavailable. Liveness should detect a process that cannot serve requests; it should not fail merely because SQLite is temporarily unavailable.

This application currently uses SQLite. These checks establish only that the configured SQLite database can execute a simple query; they do not verify backups, disk durability, write capacity, external services, or end-to-end user workflows.

## Availability target and evidence

The stated target is at least 99% availability during store operating hours, excluding planned maintenance.

Define and record:
1. The store's operating hours and timezone.
2. The measurement start and end timestamps.
3. The probe interval and timeout.
4. Planned maintenance windows, documented before exclusion.
5. Every unplanned outage and its start/end timestamps.

Calculate:

`Availability (%) = ((eligible operating minutes - unplanned unavailable minutes) / eligible operating minutes) * 100`

The target is met only when the measured result is at least 99%. Retain timestamped probe results and incident records. A passing unit-test suite or loopback performance benchmark is not operational uptime evidence.

No production monitoring observations have been supplied at the time this document was prepared. Therefore, 99% availability is a target to measure, not a result claimed as achieved.
