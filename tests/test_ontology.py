import hashlib

import pytest

from awsgraph.ontology import ROOT, DataBuilder, OntologyError
from awsgraph.schema import edge_definitions

VENDORED = {
    "aws.ttl": "9a9bda99f43494e37353f5b25941a2ae9c9ade2c84ecfc29b32dfffc5ab61cc7",
    "aws.shapes.ttl": "7611598f04f75fd9c465e5da91d58a5de9e0da0e754831e1fa90353e04473e1a",
}


@pytest.mark.parametrize("name,digest", VENDORED.items())
def test_vendored_ontology_is_pinned(name, digest):
    data = (ROOT / "ontology" / "vendor" / name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest, "update ontology/vendor/SOURCE.md and this test together"


def test_profile_terms_exist(ontology):
    # Ontology() raises if any profile class or property is missing; check a few by kind too.
    assert ontology.property_kind("hasExecutionRole") == "object"
    assert ontology.property_kind("isPubliclyAccessible") == "datatype"
    assert ontology.is_subclass("IAMRole", "IAMEntity")
    assert ontology.is_subclass("S3Bucket", "AWSResource")
    assert not ontology.is_subclass("Tag", "AWSResource")


def test_edge_definitions_follow_domain_and_range(ontology):
    defs = {d.edge_collection: d for d in edge_definitions(ontology)}
    assert defs["hasInstanceProfile"].from_vertex_collections == ["EC2Instance"]
    assert defs["hasInstanceProfile"].to_vertex_collections == ["IAMInstanceProfile"]
    assert defs["canAssumeRole"].from_vertex_collections == ["IAMRole", "IAMUser"]
    assert defs["memberOf"].to_vertex_collections == ["IAMGroup"]
    # canRead declares no domain or range of its own; it inherits them from hasEffectiveAccess
    assert "Tag" not in defs["canRead"].to_vertex_collections
    assert "IAMRole" in defs["canRead"].from_vertex_collections
    assert "Tag" not in defs["hasExecutionRole"].from_vertex_collections
    assert defs["hasExecutionRole"].to_vertex_collections == ["IAMRole"]


def test_builder_rejects_statements_outside_domain_or_range(ontology):
    b = DataBuilder(ontology)
    user = b.individual("IAMUser", "u", "u")
    bucket = b.individual("S3Bucket", "b", "b")
    role = b.individual("IAMRole", "r", "r")
    b.link(user, "canAssumeRole", role)
    with pytest.raises(OntologyError):
        b.link(bucket, "canAssumeRole", role)        # domain is IAMEntity
    with pytest.raises(OntologyError):
        b.link(user, "canAssumeRole", bucket)        # range is IAMRole
    with pytest.raises(OntologyError):
        b.attr(bucket, "isPubliclyAccessible", "yes")  # range is xsd:boolean
    with pytest.raises(OntologyError):
        b.link(user, "canRead", bucket)              # derived: only the derivation step writes it
