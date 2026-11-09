"""Step 4: load.

Loads the generated Turtle into ArangoDB with ArangoRDF's Property Graph Transformation
(PGT). PGT puts each individual in the collection named after its class, turns each object
property into an edge in the collection named after the property, and stores datatype
properties as document attributes. Document keys are the readable keys the generator
assigned (``web-role``, ``s3:GetObject``) rather than hashes.

The class of each individual is passed to PGT as an ArangoDB collection statement instead of
as ``rdf:type``, so PGT doesn't also write a ``type`` edge for it into DataGraph. The
instance-to-class link is written afterwards as a ``dataType`` edge, which only
KnowledgeGraph includes.

    python -m awsgraph load
"""

from __future__ import annotations

from pathlib import Path

from arango.database import StandardDatabase
from arango_rdf import ArangoRDF
from rdflib import RDF, Graph, Literal, URIRef

from .db import DATA_GRAPH
from .ontology import ROOT, Ontology, Profile
from .schema import TYPE_EDGE

ADB = "http://www.arangodb.com/"
ADB_KEY = URIRef(ADB + "key")
ADB_COLLECTION = URIRef(ADB + "collection")


def load(db: StandardDatabase, path: Path | None = None, profile: Profile | None = None) -> dict:
    ont = Ontology(profile)
    path = path or ROOT / "build" / "data.ttl"
    data = Graph().parse(path)
    collections = Graph()
    individuals = set(data.subjects(RDF.type, None))
    for s, cls in list(data.subject_objects(RDF.type)):
        data.remove((s, RDF.type, cls))
        data.add((s, ADB_KEY, Literal(str(s).rsplit("/", 1)[-1])))
        collections.add((s, ADB_COLLECTION, Literal(ont.local(cls))))
    # The properties the data uses are already in Property, loaded with the ontology.
    for p in set(data.predicates()) - {ADB_KEY}:
        collections.add((p, ADB_COLLECTION, Literal("Property")))
    ArangoRDF(db).rdf_to_arangodb_by_pgt(DATA_GRAPH, data, adb_col_statements=collections,
                                         write_adb_col_statements=False, overwrite_graph=False)
    return {"individuals": len(individuals), TYPE_EDGE: link_instances_to_classes(db, ont)}


def link_instances_to_classes(db: StandardDatabase, ont: Ontology) -> int:
    """One ``dataType`` edge from every instance to its ``Class`` document."""
    db.collection(TYPE_EDGE).truncate()
    total = 0
    for cls in ont.profile.all_classes:
        total += next(db.aql.execute(
            """LET cls = FIRST(FOR c IN Class FILTER c._uri == @uri RETURN c._id)
               RETURN LENGTH(FOR i IN @@instances
                               INSERT { _from: i._id, _to: cls } INTO @@edges
                               RETURN 1)""",
            bind_vars={"uri": str(ont.term(cls)), "@instances": cls, "@edges": TYPE_EDGE}))
    return total
