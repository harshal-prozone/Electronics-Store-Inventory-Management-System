#!/usr/bin/env python3
"""Sample an HTTP health endpoint and write timestamped probe results to CSV.

This is a periodic diagnostic sampler, not continuous monitoring. The result
must be interpreted using the approved SRS environment, period and method.
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
    parser.add_argument("--target-percent", type=float, default=99.0)
    parser.add_argument("--csv", default="availability-results.csv")
    args = parser.parse_args()

    if args.duration_seconds <= 0 or args.interval_seconds <= 0 or args.timeout_seconds <= 0:
        parser.error("duration, interval and timeout must all be positive")
    if not 0 < args.target_percent <= 100:
        parser.error("target-percent must be greater than 0 and at most 100")

    start_wall = datetime.now(timezone.utc)
    start_mono = time.monotonic()
    deadline = start_mono + args.duration_seconds
    total = successes = failures = 0

    with open(args.csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "timestamp_utc", "url", "success", "http_status",
            "latency_ms", "error",
        ])
        while time.monotonic() < deadline:
            probe_start = time.monotonic()
            stamp = utc_now()
            total += 1
            status: int | str = ""
            error = ""
            ok = False
            try:
                request = Request(
                    args.url,
                    headers={"User-Agent": "ESIMS-availability-probe/1.1"},
                )
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
                sleep_for = max(0.0, args.interval_seconds - (time.monotonic() - probe_start))
                time.sleep(min(sleep_for, remaining))

    end_wall = datetime.now(timezone.utc)
    elapsed = time.monotonic() - start_mono
    availability = 100.0 * successes / total if total else 0.0
    passed = total > 0 and availability >= args.target_percent

    print(f"Started (UTC): {start_wall.isoformat()}")
    print(f"Ended (UTC):   {end_wall.isoformat()}")
    print(f"Elapsed:       {elapsed:.2f} seconds")
    print(f"Probes:        {total}")
    print(f"Successful:    {successes}")
    print(f"Failed:        {failures}")
    print(f"Sampled availability: {availability:.4f}%")
    print(f"Target:        {args.target_percent:.4f}%")
    print(f"Target met by sampled probes: {'YES' if passed else 'NO'}")
    print(f"CSV:           {args.csv}")
    print("WARNING: periodic sampled ratio only; not proof of continuous or long-term uptime.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
