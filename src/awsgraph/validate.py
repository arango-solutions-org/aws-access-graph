"""Validate generated data against the ontology's SHACL shapes.

The shapes come from the vendored AWS ontology (``aws.shapes.ttl``). Violation-severity
results fail the build; Warning-severity results (such as resource types AWS gives no ARN)
are reported and allowed, as they are in the ontology's own CI.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyshacl import validate as shacl_validate
from rdflib import Graph, Namespace

from .ontology import Profile

SH = Namespace("http://www.w3.org/ns/shacl#")


@dataclass
class Report:
    conforms: bool
    violations: int
    warnings: int
    text: str


def validate(data: Graph, profile: Profile | None = None) -> Report:
    profile = profile or Profile.load()
    shapes = Graph().parse(profile.shapes_path)
    ontology = Graph().parse(profile.ontology_path)
    conforms, results, text = shacl_validate(
        data, shacl_graph=shapes, ont_graph=ontology, inference="rdfs",
        allow_warnings=True, abort_on_first=False)
    violations = len(list(results.subjects(SH.resultSeverity, SH.Violation)))
    warnings = len(list(results.subjects(SH.resultSeverity, SH.Warning)))
    return Report(conforms, violations, warnings, text)
