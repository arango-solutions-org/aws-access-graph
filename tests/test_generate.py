from collections import Counter

from rdflib import RDF

from awsgraph.generate import build
from awsgraph.validate import validate


def test_deterministic():
    a, b = build(seed=7).b.graph, build(seed=7).b.graph
    assert set(a) == set(b)


def test_every_individual_has_exactly_one_class(estate):
    g = estate.b.graph
    counts = Counter(s for s in g.subjects(RDF.type, None))
    assert set(counts.values()) == {1}


def test_conforms_to_shapes(estate):
    report = validate(estate.b.graph)
    assert report.conforms, report.text
    assert report.violations == 0


def test_scenarios_present(estate):
    for label in ["public-web-instance", "web-role", "app-role", "financial-exports", "dev-deployer-role",
                  "prod-admin-role", "breakglass-user", "etl-service-user", "migration-scratch", "contractor-user"]:
        assert label in estate.by_label


def test_no_derived_facts_in_generated_data(estate):
    ns = estate.b.ns
    for prop in estate.b.ont.profile.derived_properties:
        assert not list(estate.b.graph.triples((None, ns[prop], None)))
