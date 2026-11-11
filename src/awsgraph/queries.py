"""Step 6: queries.

Each file in ``aql/queries`` is one question. Its header holds the bind parameters as JSON
on the ``// bind:`` line (continued on following ``//`` lines); the other header comments
describe it. ``aql/visualizer`` holds a graph version of each, which returns the routes as
paths for the Graph Visualizer, and names its graph on a ``// graph:`` line. Run them all, or one:

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
VISUALIZER_DIR = ROOT / "aql" / "visualizer"


@dataclass(frozen=True)
class Query:
    id: str
    title: str
    path: Path
    text: str
    bind: dict
    description: str = ""
    graph: str | None = None


def parse(path: Path) -> Query:
    text = path.read_text()
    header = []
    for line in text.splitlines():
        if not line.startswith("//"):
            break
        header.append(line.removeprefix("//").strip())
    title, graph, bind_src, about = header[0], None, "", []
    rest = iter(header[1:])
    for line in rest:
        if line.startswith("bind:"):
            bind_src = line.removeprefix("bind:")
            while bind_src.strip() and not _is_json(bind_src):
                bind_src += " " + next(rest)
        elif line.startswith("graph:"):
            graph = line.removeprefix("graph:").strip()
        else:
            about.append(line)
    bind = json.loads(bind_src) if bind_src.strip() else {}
    return Query(path.stem.split("_")[0], title, path, text, bind, " ".join(about), graph)


def _is_json(src: str) -> bool:
    try:
        json.loads(src)
        return True
    except json.JSONDecodeError:
        return False


def all_queries() -> list[Query]:
    return [parse(p) for p in sorted(QUERY_DIR.glob("*.aql"))]


def visualizer_queries() -> list[Query]:
    return [parse(p) for p in sorted(VISUALIZER_DIR.glob("*.aql"))]


def run(db: StandardDatabase, query: Query, bind: dict | None = None) -> list:
    return list(db.aql.execute(query.text, bind_vars={**query.bind, **(bind or {})}, count=False))
