"""Step 6: queries.

Each file in ``aql/queries`` is one question. Its header holds the bind parameters as JSON
on the ``// bind:`` line (continued on following ``//`` lines). Run them all, or one:

    python -m awsgraph queries
    python -m awsgraph queries q05
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from arango.database import StandardDatabase

from .ontology import ROOT

QUERY_DIR = ROOT / "aql" / "queries"


@dataclass(frozen=True)
class Query:
    id: str
    title: str
    path: Path
    text: str
    bind: dict


def parse(path: Path) -> Query:
    text = path.read_text()
    lines = text.splitlines()
    title = lines[0].lstrip("/ ").strip()
    bind_src, collecting = "", False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("// bind:"):
            bind_src, collecting = stripped.removeprefix("// bind:"), True
        elif collecting and stripped.startswith("//"):
            try:
                json.loads(bind_src)
                break
            except json.JSONDecodeError:
                bind_src += " " + stripped.removeprefix("//")
        elif collecting:
            break
    bind = json.loads(bind_src) if bind_src.strip() else {}
    return Query(path.stem.split("_")[0], title, path, text, bind)


def all_queries() -> list[Query]:
    return [parse(p) for p in sorted(QUERY_DIR.glob("*.aql"))]


def run(db: StandardDatabase, query: Query, bind: dict | None = None) -> list:
    return list(db.aql.execute(query.text, bind_vars={**query.bind, **(bind or {})}, count=False))
