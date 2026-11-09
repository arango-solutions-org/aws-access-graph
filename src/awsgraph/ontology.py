"""Step 1: the ontology.

Loads the vendored AWS ontology and the project profile, and gives the rest of the code one
way to write data: :class:`DataBuilder`. Every individual it creates has exactly one,
declared, class, and every statement is checked against the property's ``rdfs:domain`` and
``rdfs:range`` before it is written. Data that doesn't fit the ontology can't be produced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import yaml
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[2]

_PY_TYPES = {
    XSD.string: str,
    XSD.boolean: bool,
    XSD.integer: int,
    XSD.decimal: (int, float),
    XSD.float: (int, float),
}


class OntologyError(ValueError):
    """Raised when data would not conform to the ontology."""


@dataclass(frozen=True)
class Profile:
    ontology_path: Path
    shapes_path: Path
    ns: Namespace
    data_ns: Namespace
    classes: dict[str, list[str]]
    asserted_properties: list[str]
    datatype_properties: list[str]
    derived_properties: list[str]
    tags: dict[str, str]
    sensitive_classifications: list[str]

    @classmethod
    def load(cls, path: Path | None = None) -> Profile:
        path = path or ROOT / "ontology" / "profile.yaml"
        raw = yaml.safe_load(path.read_text())
        return cls(
            ontology_path=ROOT / raw["ontology"],
            shapes_path=ROOT / raw["shapes"],
            ns=Namespace(raw["namespace"]),
            data_ns=Namespace(raw["data_namespace"]),
            classes=raw["classes"],
            asserted_properties=raw["asserted_properties"],
            datatype_properties=raw["datatype_properties"],
            derived_properties=raw["derived_properties"],
            tags=raw["tags"],
            sensitive_classifications=raw["sensitive_classifications"],
        )

    @property
    def all_classes(self) -> list[str]:
        return [c for group in self.classes.values() for c in group]


class Ontology:
    """The vendored AWS ontology, restricted to what the profile uses."""

    def __init__(self, profile: Profile | None = None):
        self.profile = profile or Profile.load()
        self.ns = self.profile.ns
        self.graph = Graph().parse(self.profile.ontology_path)
        self._check_profile()

    # -- lookups ---------------------------------------------------------------

    def term(self, name: str) -> URIRef:
        return self.ns[name]

    def local(self, uri: URIRef) -> str:
        return str(uri).removeprefix(str(self.ns))

    def is_class(self, name: str) -> bool:
        return (self.term(name), RDF.type, OWL.Class) in self.graph

    def property_kind(self, name: str) -> str | None:
        uri = self.term(name)
        if (uri, RDF.type, OWL.ObjectProperty) in self.graph:
            return "object"
        if (uri, RDF.type, OWL.DatatypeProperty) in self.graph:
            return "datatype"
        return None

    def domain(self, prop: str) -> URIRef | None:
        return self._inherited(prop, RDFS.domain)

    def range(self, prop: str) -> URIRef | None:
        return self._inherited(prop, RDFS.range)

    def _inherited(self, prop: str | None, predicate: URIRef) -> URIRef | None:
        """The property's own domain or range, else the nearest one up rdfs:subPropertyOf
        (canRead, for example, takes its domain and range from hasEffectiveAccess)."""
        seen = set()
        while prop is not None and prop not in seen:
            seen.add(prop)
            value = self.graph.value(self.term(prop), predicate)
            if value is not None:
                return value
            prop = self.super_property(prop)
        return None

    def superclasses(self, name: str) -> set[str]:
        """The class itself and all its named superclasses."""
        seen: set[str] = set()
        todo = [self.term(name)]
        while todo:
            c = todo.pop()
            if not isinstance(c, URIRef) or not str(c).startswith(str(self.ns)):
                continue
            local = self.local(c)
            if local in seen:
                continue
            seen.add(local)
            todo.extend(self.graph.objects(c, RDFS.subClassOf))
        return seen

    def is_subclass(self, name: str, of: URIRef | str) -> bool:
        target = self.local(of) if isinstance(of, URIRef) else of
        return target in self.superclasses(name)

    def super_property(self, prop: str) -> str | None:
        parent = self.graph.value(self.term(prop), RDFS.subPropertyOf)
        return self.local(parent) if parent is not None else None

    @cached_property
    def class_hierarchy(self) -> dict[str, list[str]]:
        """Each profile class mapped to its superclasses, most specific first."""
        out = {}
        for c in self.profile.all_classes:
            chain, current = [], self.term(c)
            while current is not None:
                chain.append(self.local(current))
                parents = [p for p in self.graph.objects(current, RDFS.subClassOf)
                           if isinstance(p, URIRef) and str(p).startswith(str(self.ns))]
                current = parents[0] if parents else None
            out[c] = chain
        return out

    # -- validation ------------------------------------------------------------

    def _check_profile(self) -> None:
        missing = [c for c in self.profile.all_classes if not self.is_class(c)]
        if missing:
            raise OntologyError(f"profile classes not in the ontology: {missing}")
        for p in self.profile.asserted_properties:
            if self.property_kind(p) != "object":
                raise OntologyError(f"{p} is not an object property in the ontology")
        for p in self.profile.datatype_properties:
            if self.property_kind(p) != "datatype":
                raise OntologyError(f"{p} is not a datatype property in the ontology")
        for p in self.profile.derived_properties:
            if self.property_kind(p) is None:
                raise OntologyError(f"derived property {p} is not in the ontology")

    def check_object_statement(self, prop: str, s_class: str, o_class: str) -> None:
        domain, range_ = self.domain(prop), self.range(prop)
        if domain is not None and not self.is_subclass(s_class, domain):
            raise OntologyError(f"{prop}: subject {s_class} is outside domain {self.local(domain)}")
        if range_ is not None and not self.is_subclass(o_class, range_):
            raise OntologyError(f"{prop}: object {o_class} is outside range {self.local(range_)}")

    def check_datatype_statement(self, prop: str, s_class: str, value: object) -> URIRef:
        domain, range_ = self.domain(prop), self.range(prop)
        if domain is not None and not self.is_subclass(s_class, domain):
            raise OntologyError(f"{prop}: subject {s_class} is outside domain {self.local(domain)}")
        expected = _PY_TYPES.get(range_, str)
        if isinstance(value, bool) and expected is not bool:
            raise OntologyError(f"{prop}: expected {range_}, got a boolean")
        if not isinstance(value, expected):
            raise OntologyError(f"{prop}: expected {range_}, got {type(value).__name__}")
        return range_ or XSD.string


_SLUG = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    return _SLUG.sub("-", text.lower()).strip("-")


class DataBuilder:
    """Writes instance data (the A-Box) as RDF, checked against the ontology."""

    def __init__(self, ontology: Ontology):
        self.ont = ontology
        self.ns = ontology.ns
        self.data = ontology.profile.data_ns
        self.graph = Graph()
        self.graph.bind("aws", self.ns)
        self.graph.bind("d", self.data)
        self.types: dict[URIRef, str] = {}
        self.writable = set(ontology.profile.asserted_properties) | set(ontology.profile.datatype_properties)

    def individual(self, cls: str, key: str, label: str, **attrs: object) -> URIRef:
        """Create (or return) an individual of exactly one class."""
        if cls not in self.ont.profile.all_classes:
            raise OntologyError(f"{cls} is not in the profile")
        uri = self.data[f"{slug(cls)}/{key}"]
        if uri in self.types:
            if self.types[uri] != cls:
                raise OntologyError(f"{uri} already has class {self.types[uri]}")
            return uri
        self.types[uri] = cls
        self.graph.add((uri, RDF.type, self.ns[cls]))
        self.graph.add((uri, RDFS.label, Literal(label)))
        for prop, value in attrs.items():
            if value is not None:
                self.attr(uri, prop, value)
        return uri

    def attr(self, subject: URIRef, prop: str, value: object, derived: bool = False) -> None:
        if not derived and prop not in self.writable:
            raise OntologyError(f"{prop} is not a writable property in the profile")
        datatype = self.ont.check_datatype_statement(prop, self.types[subject], value)
        self.graph.add((subject, self.ns[prop], Literal(value, datatype=datatype)))

    def link(self, subject: URIRef, prop: str, obj: URIRef, derived: bool = False) -> None:
        if not derived and prop not in self.ont.profile.asserted_properties:
            raise OntologyError(f"{prop} is not an asserted property in the profile")
        self.ont.check_object_statement(prop, self.types[subject], self.types[obj])
        self.graph.add((subject, self.ns[prop], obj))

    def class_of(self, uri: URIRef) -> str:
        return self.types[uri]

    def key_of(self, uri: URIRef) -> str:
        return str(uri).rsplit("/", 1)[-1]
