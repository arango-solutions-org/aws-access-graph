import json
from pathlib import Path

from awsgraph.sparql import run

ROOT = Path(__file__).resolve().parents[1]


def test_sparql_and_aql_agree_on_the_ontology():
    """examples/sparql/01 over the Turtle gives the same answer as Q9 over ArangoDB."""
    rows = run(ROOT / "examples" / "sparql" / "01_relationships_between_classes.rq", with_data=False)
    expected = json.loads((ROOT / "tests" / "expected" / "q09.json").read_text())
    assert [(r["property"], r["domain"], r["range"], r.get("parent")) for r in rows] == \
           [(e["property"], e["domain"], e["range"], e["parent"]) for e in expected]
