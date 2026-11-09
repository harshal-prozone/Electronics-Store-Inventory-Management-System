#!/usr/bin/env python3
"""Run Locust against a disposable 5,000-item loopback Flask/SQLite instance.

Install requirements.txt and requirements-performance.txt. Example:
python scripts/run_locust_benchmark.py --output /tmp/esims-locust --duration 5m
The synthetic data and disposable credentials are never used against a real store.
"""
import argparse
import csv
import json
import platform
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.serving import make_server
import performance_test as perf  # sets a fresh disposable database and imports app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='Output file prefix')
    parser.add_argument('--duration', default='5m')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    perf.seed_database()
    with perf.flask_app.app_context():
        count = perf.get_db().execute('SELECT COUNT(*) FROM components WHERE deleted_at IS NULL').fetchone()[0]
    server = make_server('127.0.0.1', 0, perf.flask_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    command = [sys.executable, '-m', 'locust', '-f', str(Path(__file__).with_name('locust_inventory.py')),
               '--headless', '--host', f'http://127.0.0.1:{server.server_port}', '--users', '10',
               '--spawn-rate', '10', '--run-time', args.duration, '--csv', str(output), '--only-summary']
    start = datetime.now(timezone.utc).isoformat()
    try:
        with open(str(output) + '.log', 'w', encoding='utf-8') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
    finally:
        server.shutdown()
        thread.join()
    with open(str(output) + '_stats.csv', newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    selected = [r for r in rows if r['Name'] in ('inventory list', 'inventory search')]
    summary = {'start_utc': start, 'end_utc': datetime.now(timezone.utc).isoformat(),
               'duration_requested': args.duration, 'users': 10, 'components': count,
               'environment': platform.platform(), 'python': platform.python_version(),
               'server': 'threaded Werkzeug on loopback, SQLite; synthetic data',
               'wait_seconds': 'uniform 0.2–1.0', 'list_to_search_weight': '2:1',
               'locust_exit_code': result.returncode, 'workloads': selected}
    with open(str(output) + '_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    if result.returncode or len(selected) != 2 or any(int(r['Failure Count']) or not int(r['Request Count']) or float(r['95%']) > 2000 for r in selected):
        print('FAIL: see', output, 'reports')
        return 1
    print('PASS (loopback only): see', output, 'reports')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
