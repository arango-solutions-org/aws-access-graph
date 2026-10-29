"""Connection settings, read from the environment or a ``.env`` file in the repo root."""

from __future__ import annotations

import os
from dataclasses import dataclass

from arango import ArangoClient
from arango.database import StandardDatabase

from .ontology import ROOT

# One named graph holds both the ontology (classes, properties, subClassOf, domain, range) and
# the instance data. ArangoRDF links every instance to its class with a `type` edge, and an
# edge collection can only have one definition, so the two can't be separate graphs.
GRAPH = "AWSAccessGraph"


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    url: str
    user: str
    password: str
    database: str

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv()
        return cls(
            url=os.environ.get("ARANGO_URL", "http://localhost:8529"),
            user=os.environ.get("ARANGO_USER", "root"),
            password=os.environ.get("ARANGO_PASSWORD", ""),
            database=os.environ.get("ARANGO_DB", "aws_access_graph"),
        )


def connect(create: bool = False, settings: Settings | None = None) -> StandardDatabase:
    """Open the project database, creating it first if ``create`` is set."""
    s = settings or Settings.from_env()
    client = ArangoClient(hosts=s.url, request_timeout=300)
    if create:
        system = client.db("_system", username=s.user, password=s.password)
        try:
            if not system.has_database(s.database):
                system.create_database(s.database)
        except Exception as exc:  # no rights on _system: the database must already exist
            db = client.db(s.database, username=s.user, password=s.password)
            if not db.has_collection("_graphs"):
                raise RuntimeError(f"cannot create or open database {s.database}: {exc}") from exc
    return client.db(s.database, username=s.user, password=s.password)


def reset(db: StandardDatabase) -> list[str]:
    """Drop the graph and every collection in the project database."""
    if db.name == "_system":
        raise RuntimeError("refusing to reset the _system database")
    if db.has_graph(GRAPH):
        db.delete_graph(GRAPH)
    for g in db.graphs():           # graphs left by older versions of this repo
        db.delete_graph(g["name"])
    dropped = []
    for col in db.collections():
        if not col["system"]:
            db.delete_collection(col["name"])
            dropped.append(col["name"])
    return dropped
