import hashlib

import pytest

from awsgraph.ontology import ROOT, DataBuilder, OntologyError
from awsgraph.schema import edge_definitions

VENDORED = {
    "aws.ttl": "9e253726d0604b950ea9f5066b060c326c5dd6cbc30f8954d8d123ef23529b12",
    "aws.shapes.ttl": "aa8519d77176326e491aacd350f00fb8534e7016dba2b4f99ec10946c27ddb6c",
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
    assert "Tag" not in defs["canRead"].to_vertex_collections
    assert set(defs["hasExecutionRole"].from_vertex_collections) == {"EC2Instance", "LambdaFunction"}


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
