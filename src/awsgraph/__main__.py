"""Command line: python -m awsgraph <step>.

Steps, in order: generate, validate, schema, load, derive, queries. ``all`` runs every step.
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="awsgraph", description=__doc__)
    parser.add_argument("step", choices=["generate", "validate", "schema", "load", "derive", "queries", "all", "reset"])
    parser.add_argument("query", nargs="?", help="with 'queries': run only this one, e.g. q05")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    steps = ["generate", "validate", "schema", "load", "derive", "queries"] if args.step == "all" else [args.step]
    db = None
    for step in steps:
        t = time.time()
        print(f"== {step}", flush=True)
        if step == "generate":
            from .generate import write
            path, g = write(seed=args.seed)
            print(f"wrote {len(g)} triples to {path}")
        elif step == "validate":
            from rdflib import Graph

            from .ontology import ROOT
            from .validate import validate
            report = validate(Graph().parse(ROOT / "build" / "data.ttl"))
            print(f"SHACL: {report.violations} violations, {report.warnings} warnings (expected by design)")
            if not report.conforms:
                print(report.text)
                return 1
        else:
            from .db import connect
            db = db or connect(create=step in ("schema", "reset"))
            if step == "reset":
                from .db import GRAPH, ONTOLOGY_GRAPH
                for name in (GRAPH, ONTOLOGY_GRAPH):
                    if db.has_graph(name):
                        db.delete_graph(name, drop_collections=True)
                print("dropped both graphs and their collections")
            elif step == "schema":
                from .schema import create, load_ontology
                print(create(db))
                load_ontology(db)
                print("loaded the ontology into the AWSOntology graph")
            elif step == "load":
                from .load import load
                print(load(db))
            elif step == "derive":
                from .derive import derive
                print(json.dumps(derive(db), indent=2))
            elif step == "queries":
                from .queries import all_queries, run
                for q in all_queries():
                    if args.query and q.id != args.query:
                        continue
                    rows = run(db, q)
                    print(f"\n-- {q.title}  ({len(rows)} rows)")
                    for row in rows:
                        print(json.dumps(row))
        print(f"   {time.time() - t:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
