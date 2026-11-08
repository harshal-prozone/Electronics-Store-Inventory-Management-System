\
#!/usr/bin/env python3
"""Sample an HTTP health endpoint and write timestamped probe results to CSV.

This is a diagnostic sampler, not continuous monitoring. Use the measurement
method and observation period required by the project's approved SRS.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5000/health")
    parser.add_argument("--duration-seconds", type=int, default=3600)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=3.0)
    parser.add_argument("--csv", default="availability-results.csv")
    args = parser.parse_args()

    if args.duration_seconds <= 0 or args.interval_seconds <= 0 or args.timeout_seconds <= 0:
        parser.error("duration, interval and timeout must all be positive")

    started = time.monotonic()
    deadline = started + args.duration_seconds
    total = successes = failures = 0

    with open(args.csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp_utc", "url", "success", "http_status", "latency_ms", "error"])
        while time.monotonic() < deadline:
            probe_start = time.monotonic()
            stamp = utc_now()
            total += 1
            status = ""
            error = ""
            ok = False
            try:
                request = Request(args.url, headers={"User-Agent": "ESIMS-availability-probe/1.0"})
                with urlopen(request, timeout=args.timeout_seconds) as response:
                    status = response.status
                    body = response.read(65536)
                    ok = 200 <= response.status < 300 and bool(body)
                    if not ok:
                        error = "non-2xx response or empty body"
            except HTTPError as exc:
                status = exc.code
                error = f"HTTPError: {exc}"
            except (URLError, TimeoutError, OSError) as exc:
                error = f"{type(exc).__name__}: {exc}"

            latency_ms = round((time.monotonic() - probe_start) * 1000, 2)
            successes += int(ok)
            failures += int(not ok)
            writer.writerow([stamp, args.url, int(ok), status, latency_ms, error])
            handle.flush()

            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(max(0.0, args.interval_seconds - (time.monotonic() - probe_start)), remaining))

    availability = 100.0 * successes / total if total else 0.0
    print(f"Started: {datetime.fromtimestamp(time.time() - args.duration_seconds, timezone.utc).isoformat()} (nominal)")
    print(f"Probes: {total}; successful: {successes}; failed: {failures}")
    print(f"Sampled availability: {availability:.4f}%")
    print(f"CSV: {args.csv}")
    print("NOTE: sampled probe ratio only; interpret using the approved SRS measurement method.")
    return 0 if total and failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
