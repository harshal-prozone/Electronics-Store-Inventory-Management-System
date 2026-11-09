#!/usr/bin/env python3
"""Measure 10 dashboard loads on a disposable 5,000-component local database.

This is a sequential loopback diagnostic, not a production or original-stack
performance test. Uses the seed and temporary app setup from performance_test.
"""
import json
import logging
import threading
import time
from urllib.request import Request, urlopen

from werkzeug.serving import make_server
import performance_test as perf


def main():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    admin = perf.seed_database()
    signer = perf.flask_app.session_interface.get_signing_serializer(perf.flask_app)
    if signer is None:
        raise RuntimeError("Cannot sign the disposable test session")
    cookie = signer.dumps({"_permanent": True, "user_id": admin})
    server = make_server("127.0.0.1", 0, perf.flask_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        durations = []
        for _ in range(10):
            request = Request(
                f"http://127.0.0.1:{server.server_port}/",
                headers={"Cookie": f"{perf.flask_app.config['SESSION_COOKIE_NAME']}={cookie}"},
            )
            start = time.perf_counter()
            with urlopen(request, timeout=10) as response:
                body = response.read()
                if response.status != 200 or b"Stock by category" not in body:
                    raise RuntimeError("Dashboard did not return the expected chart")
            durations.append(round((time.perf_counter() - start) * 1000, 2))
        result = {
            "components": 5000, "requests": 10, "successful": len(durations),
            "latency_ms": durations, "max_ms": max(durations),
            "all_under_2s": all(ms < 2000 for ms in durations),
            "environment": "synthetic loopback threaded Flask/Werkzeug/SQLite; sequential requests; not production or original stack",
        }
        print(json.dumps(result, indent=2))
        return 0 if result["all_under_2s"] else 1
    finally:
        server.shutdown()
        thread.join()


if __name__ == "__main__":
    raise SystemExit(main())
