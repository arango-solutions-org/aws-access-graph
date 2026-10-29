"""Run a SPARQL example over the ontology and the generated data, locally with rdflib.

    python -m awsgraph.sparql examples/sparql/01_relationships_between_classes.rq
"""

from __future__ import annotations

import sys
from pathlib import Path

from rdflib import Graph

from .ontology import ROOT, Profile


def run(path: Path, with_data: bool = True) -> list[dict]:
    g = Graph().parse(Profile.load().ontology_path)
    data = ROOT / "build" / "data.ttl"
    if with_data and data.exists():
        g.parse(data)
    rows = g.query(Path(path).read_text())
    return [{str(k): (str(v) if v is not None else None) for k, v in row.asdict().items()} for row in rows]


if __name__ == "__main__":
    for row in run(Path(sys.argv[1])):
        print(row)
