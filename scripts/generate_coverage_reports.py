#!/usr/bin/env python3
"""Generate Markdown line- and branch-coverage reports from coverage.py JSON."""
import json, os
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "coverage.json"
docs = root / "docs"

def pct(hit, total):
    return f"{100 * hit / total:.2f}%" if total else "N/A (no measurable branches/statements)"

if not source.exists():
    raise SystemExit("coverage.json missing; run pytest with pytest-cov first")
data = json.loads(source.read_text(encoding="utf-8"))
totals, files = data.get("totals", {}), data.get("files", {})
stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
commit = os.getenv("GITHUB_SHA", "local run; commit not supplied")
line_rows, branch_rows = [], []
for name, item in sorted(files.items()):
    s = item.get("summary", {})
    lines, stmts = int(s.get("covered_lines", 0)), int(s.get("num_statements", 0))
    branches, hit = int(s.get("num_branches", 0)), int(s.get("covered_branches", 0))
    line_rows.append(f"| `{name}` | {lines}/{stmts} | {pct(lines, stmts)} |")
    branch_rows.append(f"| `{name}` | {hit}/{branches} | {pct(hit, branches)} |")
docs.mkdir(exist_ok=True)
lc, lt = int(totals.get("covered_lines", 0)), int(totals.get("num_statements", 0))
bc, bt = int(totals.get("covered_branches", 0)), int(totals.get("num_branches", 0))
partial = int(totals.get("num_partial_branches", 0))
(docs / "Code-Coverage-Report.md").write_text(
    f"# Code Coverage Report\n\n**Generated:** {stamp}  \n**Commit:** `{commit}`\n\n"
    "| Metric | Covered | Total | Coverage |\n|---|---:|---:|---:|\n"
    f"| Executable statements | {lc} | {lt} | {pct(lc, lt)} |\n\n"
    "## Per-file results\n\n| Source file | Covered/total statements | Line coverage |\n|---|---:|---:|\n"
    + "\n".join(line_rows) + "\n\nDetailed HTML/JSON output is retained as a workflow artifact.\n",
    encoding="utf-8")
(docs / "Branch-Coverage-Report.md").write_text(
    f"# Branch Coverage Report\n\n**Generated:** {stamp}  \n**Commit:** `{commit}`\n\n"
    "| Metric | Covered | Total | Coverage |\n|---|---:|---:|---:|\n"
    f"| Branches | {bc} | {bt} | {pct(bc, bt)} |\n| Partial branches | {partial} | — | — |\n\n"
    "## Per-file results\n\n| Source file | Covered/total branches | Branch coverage |\n|---|---:|---:|\n"
    + "\n".join(branch_rows) + "\n\nFiles with no measurable branches are N/A, not 100%. HTML/JSON retained as workflow artifact.\n",
    encoding="utf-8")
