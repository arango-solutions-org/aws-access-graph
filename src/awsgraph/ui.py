"""Step 7: save the queries in the database, for the Arango web UI.

* The questions in ``aql/queries`` go to the query editor's saved queries
  (``_editor_saved_queries``), with their default bind parameters, and return tables.
* Their graph versions in ``aql/visualizer`` go to the Graph Visualizer's Queries panel
  (``_queries``) for the graph each one names, and return the routes as paths to draw. The
  panel only lists queries linked to one of the graph's viewpoints (``_viewpointQueries``),
  so this also makes sure each graph has its Default viewpoint.

Every document this step writes has a key starting ``awsgraph_``, so running it again
replaces them, and a query deleted from the repo is deleted from the database too. Anything
else in those collections, such as queries saved by hand in the UI, is left alone.

    python -m awsgraph ui
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from arango.database import StandardDatabase

from .queries import Query, all_queries, visualizer_queries

PREFIX = "awsgraph_"


def install(db: StandardDatabase) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    for name, edge in [("_editor_saved_queries", False), ("_queries", False),
                       ("_viewpoints", False), ("_viewpointQueries", True)]:
        if not db.has_collection(name):
            db.create_collection(name, edge=edge, system=True)

    editor = {f"{PREFIX}{q.id}": {
        "title": _name(q), "name": _name(q), "description": q.description,
        "content": q.text, "value": q.text,          # the editor reads one or the other by version
        "bindVariables": q.bind, "databaseName": db.name,
    } for q in all_queries()}
    _replace_all(db.collection("_editor_saved_queries"), editor, now)

    panel = {}
    for q in visualizer_queries():
        if not db.has_graph(q.graph):
            raise RuntimeError(f"{q.path.name}: graph {q.graph} doesn't exist; run make schema first")
        panel[_slug(f"{PREFIX}{q.graph}_{q.id}")] = {
            "name": _name(q), "title": _name(q), "description": q.description,
            "graphId": q.graph, "queryText": q.text, "bindVariables": q.bind,
        }
    links = db.collection("_viewpointQueries")
    _replace_all(db.collection("_queries"), panel, now, links)
    for key, doc in panel.items():
        viewpoint = _default_viewpoint(db, doc["graphId"], now)
        if not list(links.find({"_from": viewpoint, "_to": f"_queries/{key}"}, limit=1)):
            links.insert({"_from": viewpoint, "_to": f"_queries/{key}", "createdAt": now, "updatedAt": now})
    return {"editor": len(editor), "visualizer": len(panel)}


def _name(q: Query) -> str:
    return re.sub(r"\s+", " ", q.title)


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_")


def _replace_all(col, docs: dict[str, dict], now: str, links=None) -> None:
    """Make this repo's documents in ``col`` exactly ``docs``, keeping each one's createdAt.
    ``links`` is the edge collection whose edges to a deleted document go with it."""
    for old in col.all():
        key = old["_key"]
        if not key.startswith(PREFIX):
            continue
        if key not in docs:
            col.delete(key)
            for link in (links.find({"_to": old["_id"]}) if links is not None else []):
                links.delete(link)
        else:
            docs[key]["createdAt"] = old.get("createdAt", now)
    for key, doc in docs.items():
        doc = {"_key": key, "createdAt": now, **doc, "updatedAt": now}
        if col.has(key):
            col.replace(doc, check_rev=False)
        else:
            col.insert(doc)


def _default_viewpoint(db: StandardDatabase, graph: str, now: str) -> str:
    """The _id of the graph's Default viewpoint, which the UI creates when the graph is first
    opened. Created here if the graph hasn't been opened yet."""
    viewpoints = db.collection("_viewpoints")
    for doc in viewpoints.find({"graphId": graph, "name": "Default"}, limit=1):
        return doc["_id"]
    return viewpoints.insert({"graphId": graph, "name": "Default",
                              "description": "Default viewpoint for the graph",
                              "createdAt": now, "updatedAt": now})["_id"]
