"""Step 3: schema.

Turns the ontology profile into an ArangoDB schema:

* one vertex collection per class (``IAMRole``, ``S3Bucket``, ...);
* one edge collection per object property (``canAssumeRole``, ``hasRole``, ``canRead``, ...);
* a named graph whose edge definitions come straight from each property's ``rdfs:domain``
  and ``rdfs:range``: an edge collection may connect exactly the profile classes that fall
  under its domain and range;
* indexes on the attributes the queries filter on.

The collection and attribute names are the ontology's own, so a query reads like the
ontology. That named graph is ``DataGraph``. This module also loads the ontology itself (the
T-Box) with ArangoRDF into ``OntologyGraph``, and defines ``KnowledgeGraph``, which combines
the two: every edge definition of both graphs, plus a ``dataType`` edge from each instance to
its class (filled in by the load step).

    python -m awsgraph schema
"""

from __future__ import annotations

from dataclasses import dataclass

from arango.database import StandardDatabase

from .db import DATA_GRAPH, KNOWLEDGE_GRAPH, ONTOLOGY_GRAPH
from .ontology import Ontology

# Instance -> class. Not ArangoRDF's `type`, which stays in OntologyGraph for the ontology's own
# rdf:type statements (a class is an owl:Class, a property an owl:ObjectProperty, ...).
TYPE_EDGE = "dataType"


@dataclass(frozen=True)
class EdgeDefinition:
    edge_collection: str
    from_vertex_collections: list[str]
    to_vertex_collections: list[str]

    def as_dict(self) -> dict:
        return {"edge_collection": self.edge_collection,
                "from_vertex_collections": self.from_vertex_collections,
                "to_vertex_collections": self.to_vertex_collections}


def edge_definitions(ont: Ontology) -> list[EdgeDefinition]:
    """One edge definition per object property, from its domain and range."""
    classes = ont.profile.all_classes
    out = []
    for prop in ont.profile.asserted_properties + [p for p in ont.profile.derived_properties
                                                    if ont.property_kind(p) == "object"]:
        domain, range_ = ont.domain(prop), ont.range(prop)
        froms = sorted(c for c in classes if domain is None or ont.is_subclass(c, domain))
        tos = sorted(c for c in classes if range_ is None or ont.is_subclass(c, range_))
        out.append(EdgeDefinition(prop, froms, tos))
    return out


def indexes(ont: Ontology) -> dict[str, list[dict]]:
    """Persistent indexes for each vertex collection."""
    out: dict[str, list[dict]] = {c: [] for c in ont.profile.all_classes}
    for c in ont.profile.all_classes:
        supers = ont.superclasses(c)
        if "AWSResource" in supers:
            out[c].append({"fields": ["arn"], "unique": True, "sparse": True, "name": "by_arn"})
            out[c].append({"fields": ["environment"], "name": "by_environment"})
        if c in ("EC2Instance", "LambdaFunction") or "DatabaseResource" in supers or "StorageResource" in supers:
            out[c].append({"fields": ["isPubliclyAccessible"], "name": "by_public"})
        if "DatabaseResource" in supers or "StorageResource" in supers or c == "SecretsManagerSecret":
            out[c].append({"fields": ["dataClassification"], "name": "by_classification"})
    out["Tag"].append({"fields": ["tagKey", "tagValue"], "unique": True, "name": "by_key_value"})
    out["Action"].append({"fields": ["label"], "unique": True, "name": "by_name"})
    out["Action"].append({"fields": ["accessLevel"], "name": "by_access_level"})
    return out


def create(db: StandardDatabase, ont: Ontology | None = None, reset: bool = False) -> dict:
    """Create collections, indexes and the data graph. Safe to run again."""
    ont = ont or Ontology()
    if reset:
        if db.has_graph(KNOWLEDGE_GRAPH):
            db.delete_graph(KNOWLEDGE_GRAPH)
        if db.has_graph(DATA_GRAPH):
            db.delete_graph(DATA_GRAPH, drop_collections=True)
    defs = edge_definitions(ont)
    for c in ont.profile.all_classes:
        if not db.has_collection(c):
            db.create_collection(c)
    for d in defs:
        if not db.has_collection(d.edge_collection):
            db.create_collection(d.edge_collection, edge=True)
    for c, specs in indexes(ont).items():
        col = db.collection(c)
        existing = {i.get("name") for i in col.indexes()}
        for spec in specs:
            if spec["name"] not in existing:
                col.add_index({"type": "persistent", **spec})
    if not db.has_graph(DATA_GRAPH):
        used = {v for d in defs for v in d.from_vertex_collections + d.to_vertex_collections}
        db.create_graph(DATA_GRAPH, edge_definitions=[d.as_dict() for d in defs],
                        orphan_collections=sorted(set(ont.profile.all_classes) - used))
    return {"vertex_collections": len(ont.profile.all_classes), "edge_collections": len(defs)}


def load_ontology(db: StandardDatabase, ont: Ontology | None = None) -> None:
    """Load the ontology (classes, properties, domain, range, subClassOf) with ArangoRDF."""
    from arango_rdf import ArangoRDF
    from rdflib import Graph
    from rdflib.compare import to_canonical_graph

    ont = ont or Ontology()
    # A copy, because ArangoRDF modifies the graph it is given. Canonical blank-node labels
    # (OWL restrictions are blank nodes) give them the same document keys on every load, so
    # loading again overwrites them instead of adding duplicates.
    tbox = Graph()
    tbox += to_canonical_graph(ont.graph)
    ArangoRDF(db).rdf_to_arangodb_by_pgt(ONTOLOGY_GRAPH, tbox, overwrite_graph=False)


def create_knowledge_graph(db: StandardDatabase, ont: Ontology | None = None) -> dict:
    """Define KnowledgeGraph: the data graph, the ontology graph, and ``dataType`` edges from
    each instance collection to ``Class``. Run after the ontology is loaded. Safe to run again.

    The ontology's edge definitions are read back from OntologyGraph rather than written out
    here, because ArangoRDF decides them and a collection shared by two graphs must have the
    same definition in both."""
    ont = ont or Ontology()
    if not db.has_collection(TYPE_EDGE):
        db.create_collection(TYPE_EDGE, edge=True)
    defs = (db.graph(DATA_GRAPH).edge_definitions()
            + [{"edge_collection": TYPE_EDGE, "from_vertex_collections": sorted(ont.profile.all_classes),
                "to_vertex_collections": ["Class"]}]
            + db.graph(ONTOLOGY_GRAPH).edge_definitions())
    if db.has_graph(KNOWLEDGE_GRAPH):
        db.delete_graph(KNOWLEDGE_GRAPH)
    db.create_graph(KNOWLEDGE_GRAPH, edge_definitions=defs)
    return {"edge_definitions": len(defs)}
