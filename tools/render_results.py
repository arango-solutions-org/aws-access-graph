"""Render docs/RESULTS.md from tests/expected/*.json.

The expected results are what the end-to-end test checks against a live ArangoDB in CI, so the
page always shows verified output. Run after `UPDATE_EXPECTED=1 make e2e`:

    python tools/render_results.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from awsgraph.queries import all_queries  # noqa: E402

EXPECTED = ROOT / "tests" / "expected"
OUT = ROOT / "docs" / "RESULTS.md"


def cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return "<br>".join(cell(v) for v in value) if value and isinstance(value[0], (dict, list)) \
            else ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {cell(v)}" for k, v in value.items())
    return str(value).replace("|", "\\|")


def table(rows: list[dict]) -> str:
    if not rows:
        return "_No rows._\n"
    cols = list(dict.fromkeys(k for r in rows for k in r))
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(cell(r.get(c)) for c in cols) + " |" for r in rows]
    return "\n".join(out) + "\n"


def render() -> str:
    parts = [
        "# Results\n",
        "Output of every query on the demo data (`make all`, seed 42), with the bind parameters in each",
        "query file. These are generated from `tests/expected/`, which the end-to-end test checks against",
        "a live ArangoDB in CI. Don't edit this page by hand: run `python tools/render_results.py`.\n",
    ]
    for q in all_queries():
        path = EXPECTED / f"{q.id}.json"
        if not path.exists():
            continue
        rows = json.loads(path.read_text())
        num = q.id.lstrip("q").lstrip("0")
        title = q.title.split(None, 1)[1] if q.title.upper().startswith("Q") else q.title
        parts.append(f'<a id="q{num}"></a>\n## Q{num}. {title}\n')
        parts.append(f"[`{q.path.name}`](../aql/queries/{q.path.name}) · bind: `{json.dumps(q.bind)}` "
                     f"· {len(rows)} row{'s' if len(rows) != 1 else ''}\n")
        if q.id == "q05":
            parts.append(table(rows[0]["routes"]))
            parts.append("**On every route:** " + ", ".join(f"`{x}`" for x in rows[0]["onEveryRoute"]) + "\n")
        elif q.id == "q10":
            parts.append(table([{"category": r["category"], "instances": r["instances"],
                                 "by class": ", ".join(f"{c['class']} {c['instances']}" for c in r["byClass"])}
                                for r in rows]))
        else:
            parts.append(table(rows))
    return "\n".join(parts)


if __name__ == "__main__":
    OUT.write_text(render())
    print(f"wrote {OUT}")
