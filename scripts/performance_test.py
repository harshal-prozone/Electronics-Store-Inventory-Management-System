#!/usr/bin/env python3
"""Repeatable HTTP load check for Sprint 1 inventory search/listing requirements.

Creates an isolated SQLite database with at least 5,000 active components, starts
Flask's threaded WSGI server on loopback, then issues 100 authenticated HTTP requests
using 10 concurrent workers. It reports actual timing results and exits non-zero if
any request fails or fewer than 95% finish within two seconds.

This is a repeatable coursework acceptance test, not a substitute for measuring the
production deployment over its real network and infrastructure.
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Configure a disposable database before importing app.py (which creates its app
# object at module import time). Never touch the developer's ordinary database.
_tmp = tempfile.TemporaryDirectory(prefix="esims-sprint1-load-")
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "sprint1-load-test-only-not-for-real-use"
os.environ["DATABASE_PATH"] = str(Path(_tmp.name) / "load-test.sqlite")
os.environ.pop("ADMIN_PASSWORD", None)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from werkzeug.security import generate_password_hash  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from app import app as flask_app, get_db  # noqa: E402

COMPONENT_TARGET = 5_000
CONCURRENT_USERS = 10
REQUEST_COUNT = 100
TIMEOUT_SECONDS = 10.0
ACCEPTANCE_SECONDS = 2.0


def seed_database() -> int:
    with flask_app.app_context():
        db = get_db()
        user = db.execute("SELECT id FROM users WHERE username = ?", ("load-admin",)).fetchone()
        if user is None:
            cursor = db.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'Admin')",
                ("load-admin", "load-admin@example.invalid", generate_password_hash("LoadTestOnly123!")),
            )
            admin_id = int(cursor.lastrowid)
        else:
            admin_id = int(user["id"])

        active_count = int(db.execute(
            "SELECT COUNT(*) FROM components WHERE deleted_at IS NULL"
        ).fetchone()[0])
        remaining = max(COMPONENT_TARGET - active_count, 0)
        if remaining:
            first_index = int(db.execute("SELECT COUNT(*) FROM components").fetchone()[0])
            records = []
            for i in range(first_index, first_index + remaining):
                records.append((
                    f"PERF-{i:06d}",
                    f"Performance Component {i:06d}",
                    "Generated record for the Sprint 1 performance acceptance test",
                    "Performance",
                    "Benchmark Supplier",
                    100,
                    10,
                    1.0,
                ))
            db.executemany(
                """INSERT INTO components
                   (sku, name, description, category, supplier, quantity, reorder_level, unit_price)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                records,
            )
        db.commit()
        final_count = int(db.execute(
            "SELECT COUNT(*) FROM components WHERE deleted_at IS NULL"
        ).fetchone()[0])
        if final_count < COMPONENT_TARGET:
            raise RuntimeError(f"Only {final_count} active components were seeded")
        return admin_id


def main() -> int:
    try:
        admin_id = seed_database()
        serializer = flask_app.session_interface.get_signing_serializer(flask_app)
        if serializer is None:
            raise RuntimeError("Flask could not create a test-session signer")
        cookie_value = serializer.dumps({"_permanent": True, "user_id": admin_id})

        server = make_server("127.0.0.1", 0, flask_app, threaded=True)
        base_url = f"http://127.0.0.1:{server.server_port}"
        thread = threading.Thread(target=server.serve_forever, name="sprint1-load-server", daemon=True)
        thread.start()
        time.sleep(0.1)

        paths = [
            "/components",
            "/components?" + urlencode({"page": "250"}),
            "/components?" + urlencode({"q": "Performance Component 001234"}),
            "/components?" + urlencode({"q": "no-such-load-test-item"}),
            "/components?" + urlencode({
                "category": "Performance",
                "supplier": "Benchmark Supplier",
                "status": "In Stock",
            }),
        ]

        def do_request(index: int) -> tuple[float, int | None, str | None]:
            path = paths[index % len(paths)]
            request = Request(
                base_url + path,
                headers={
                    "Cookie": f"{flask_app.config.get('SESSION_COOKIE_NAME', 'session')}={cookie_value}",
                    "User-Agent": "ESIMS-Sprint1-Performance-Test/1.0",
                },
            )
            started = time.perf_counter()
            try:
                with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                    response.read()
                    elapsed = time.perf_counter() - started
                    if response.status != 200:
                        return elapsed, response.status, f"HTTP status {response.status} for {path}"
                    return elapsed, response.status, None
            except HTTPError as exc:
                return time.perf_counter() - started, exc.code, f"HTTP {exc.code} for {path}"
            except (URLError, TimeoutError, OSError) as exc:
                return time.perf_counter() - started, None, f"{type(exc).__name__} for {path}: {exc}"

        results: list[tuple[float, int | None, str | None]] = []
        with ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as pool:
            futures = [pool.submit(do_request, i) for i in range(REQUEST_COUNT)]
            for future in as_completed(futures):
                results.append(future.result())

        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

        elapsed_seconds = sorted(result[0] for result in results)
        errors = [result[2] for result in results if result[2] is not None]
        p95_index = max(0, math.ceil(0.95 * len(elapsed_seconds)) - 1)
        within_two_seconds = sum(value <= ACCEPTANCE_SECONDS for value in elapsed_seconds)
        summary = {
            "active_components": COMPONENT_TARGET,
            "concurrent_users": CONCURRENT_USERS,
            "http_requests": REQUEST_COUNT,
            "successful_requests": REQUEST_COUNT - len(errors),
            "failed_requests": len(errors),
            "p50_ms": round(elapsed_seconds[len(elapsed_seconds) // 2] * 1000, 2),
            "p95_ms": round(elapsed_seconds[p95_index] * 1000, 2),
            "max_ms": round(max(elapsed_seconds) * 1000, 2),
            "requests_within_2s_percent": round(within_two_seconds * 100 / REQUEST_COUNT, 2),
            "acceptance_target": "at least 95% of listing/search requests complete within 2 seconds",
            "result": "PASS" if not errors and within_two_seconds / REQUEST_COUNT >= 0.95 else "FAIL",
            "error_samples": errors[:5],
            "environment_note": "loopback threaded Flask WSGI server with temporary SQLite database",
        }
        print(json.dumps(summary, indent=2))
        return 0 if summary["result"] == "PASS" else 1
    finally:
        _tmp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
