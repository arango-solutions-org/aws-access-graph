"""generate -> schema -> load -> derive -> queries against a real ArangoDB.

Needs ARANGO_URL / ARANGO_USER / ARANGO_PASSWORD / ARANGO_DB (or .env). Uses its own
database, which it recreates. Run with:  pytest -m e2e
Set UPDATE_EXPECTED=1 to rewrite tests/expected/*.json from the current results.
"""

import json
import os
from pathlib import Path

import pytest

from awsgraph import queries as q
from awsgraph.db import connect, reset
from awsgraph.derive import DERIVED_EDGES, derive
from awsgraph.generate import write
from awsgraph.load import load
from awsgraph.policy_eval import derive as derive_in_python
from awsgraph.schema import create, create_knowledge_graph, load_ontology

pytestmark = pytest.mark.e2e
EXPECTED = Path(__file__).resolve().parents[1] / "expected"


@pytest.fixture(scope="module")
def db():
    database = connect(create=True)
    reset(database)
    path, graph = write()
    create(database)
    load_ontology(database)
    create_knowledge_graph(database)
    load(database, path)
    stats = derive(database)
    database.stats_ = stats
    database.graph_ = graph
    return database


def test_derived_edges_match_reference_rules(db):
    from awsgraph.ontology import Profile
    expected = derive_in_python(db.graph_, Profile.load().ns)
    actual = set()
    for edge in DERIVED_EDGES:
        for row in db.aql.execute(
                f"FOR e IN {edge} RETURN [DOCUMENT(e._from).label, DOCUMENT(e._to).label]"):
            actual.add((edge, row[0], row[1]))
    assert actual == set(expected.edges)
    levels = {(row[0], row[1]): set(row[2]) for row in db.aql.execute(
        "FOR e IN hasEffectiveAccess RETURN [DOCUMENT(e._from).label, DOCUMENT(e._to).label, e.levels]")}
    assert levels == {(frm, to): prov["levels"] for (e, frm, to), prov in expected.edges.items()
                      if e == "hasEffectiveAccess"}
    admins = set(db.aql.execute(
        "FOR x IN UNION((FOR u IN IAMUser RETURN u), (FOR r IN IAMRole RETURN r)) "
        "FILTER x.isAdministrator == true RETURN x.label"))
    assert admins == expected.admins


@pytest.mark.parametrize("query", q.all_queries(), ids=lambda x: x.id)
def test_query_results(db, query):
    rows = q.run(db, query)
    path = EXPECTED / f"{query.id}.json"
    if os.environ.get("UPDATE_EXPECTED"):
        EXPECTED.mkdir(exist_ok=True)
        path.write_text(json.dumps(rows, indent=2) + "\n")
    if not path.exists():
        pytest.fail(f"no expected results for {query.id}: run with UPDATE_EXPECTED=1 and review the diff")
    assert rows == json.loads(path.read_text())


@pytest.mark.parametrize("query", q.visualizer_queries(), ids=lambda x: x.id)
def test_visualizer_query_returns_paths_in_its_graph(db, query):
    rows = q.run(db, query)
    assert rows, "the Graph Visualizer would draw nothing"
    edges = {d["edge_collection"] for d in db.graph(query.graph).edge_definitions()}
    for p in rows:
        assert p["edges"], "a path with no edges"
        assert {e["_id"].split("/")[0] for e in p["edges"]} <= edges, f"edges outside {query.graph}"


def test_ui_install_is_idempotent(db):
    from awsgraph.ui import PREFIX, install

    def ours():
        return {name: sorted(d["_key"] for d in db.collection(name).all() if d["_key"].startswith(PREFIX))
                for name in ("_editor_saved_queries", "_queries")}

    assert install(db) == {"editor": 10, "visualizer": 10}
    first = ours()
    install(db)
    assert ours() == first
    linked = {e["_to"] for e in db.collection("_viewpointQueries").all()}
    assert {f"_queries/{k}" for k in first["_queries"]} <= linked
    assert db.collection("_viewpointQueries").count() == len(
        {(e["_from"], e["_to"]) for e in db.collection("_viewpointQueries").all()})
