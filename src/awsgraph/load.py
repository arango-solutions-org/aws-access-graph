"""Step 4: load.

Loads the generated Turtle into ArangoDB with ArangoRDF's Property Graph Transformation
(PGT). PGT puts each individual in the collection named after its class, turns each object
property into an edge in the collection named after the property, and stores datatype
properties as document attributes. Document keys are the readable keys the generator
assigned (``web-role``, ``s3:GetObject``) rather than hashes.

    python -m awsgraph load
"""

from __future__ import annotations

from pathlib import Path

from arango.database import StandardDatabase
from arango_rdf import ArangoRDF
from rdflib import RDF, Graph, Literal, URIRef

from .db import GRAPH
from .ontology import ROOT, Profile

ADB_KEY = URIRef("http://www.arangodb.com/key")


def load(db: StandardDatabase, path: Path | None = None, profile: Profile | None = None) -> dict:
    profile = profile or Profile.load()
    path = path or ROOT / "build" / "data.ttl"
    data = Graph().parse(path)
    individuals = set(data.subjects(RDF.type, None))
    for s in individuals:
        data.add((s, ADB_KEY, Literal(str(s).rsplit("/", 1)[-1])))
    ArangoRDF(db).rdf_to_arangodb_by_pgt(GRAPH, data, overwrite_graph=False)
    return {"individuals": len(individuals)}
