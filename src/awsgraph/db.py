"""Connection settings, read from the environment or a ``.env`` file in the repo root."""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests
import urllib3
from arango import ArangoClient
from arango.database import StandardDatabase

from .ontology import ROOT

# Three named graphs over one database, as in Arango's Risk Intelligence demo:
# the ontology (classes, properties, subClassOf, domain, range), the instance data, and a
# knowledge graph that combines the two and links every instance to its class with a
# `dataType` edge. A collection used by more than one graph has the same edge definition in each.
ONTOLOGY_GRAPH = "OntologyGraph"
DATA_GRAPH = "DataGraph"
KNOWLEDGE_GRAPH = "KnowledgeGraph"


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
    # False skips certificate checks; a path is a CA bundle to check against. The local install's
    # self-signed certificate names only in-cluster hosts, so it needs False.
    verify: bool | str = True

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv()
        verify: bool | str = os.environ.get("ARANGO_VERIFY_SSL", "true").strip().lower() not in ("false", "0", "no")
        if verify and os.environ.get("ARANGO_SSL_CERT_PATH"):
            verify = os.environ["ARANGO_SSL_CERT_PATH"]
        return cls(
            url=os.environ.get("ARANGO_URL", "https://127.0.0.1:8529"),
            user=os.environ.get("ARANGO_USER", "root"),
            password=os.environ.get("ARANGO_PASSWORD", ""),
            database=os.environ.get("ARANGO_DB", "aws_access_graph"),
            verify=verify,
        )


def connect(create: bool = False, settings: Settings | None = None) -> StandardDatabase:
    """Open the project database, creating it first if ``create`` is set."""
    s = settings or Settings.from_env()
    if s.verify is False:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)   # once, not per request
    _check_reachable(s)
    client = ArangoClient(hosts=s.url, request_timeout=300, verify_override=s.verify)
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


def _check_reachable(s: Settings) -> None:
    """Fail with a plain explanation, rather than python-arango's "Can't connect to host(s)",
    which it gives alike for a stopped port-forward, a rejected certificate and a bad password."""
    try:
        r = requests.get(f"{s.url}/_api/version", auth=(s.user, s.password), verify=s.verify, timeout=10)
    except requests.exceptions.SSLError as exc:
        raise RuntimeError(f"{s.url}: certificate check failed. For the local install, whose certificate is "
                           f"self-signed, set ARANGO_VERIFY_SSL=false in .env. ({exc})") from None
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"{s.url}: nothing is answering. For the local install, start the port-forward "
                           f"with `make forward` and leave it running.") from None
    if r.status_code == 401:
        raise RuntimeError(f"{s.url}: user {s.user!r} was refused. Check ARANGO_USER and ARANGO_PASSWORD in .env.")


def reset(db: StandardDatabase) -> list[str]:
    """Drop every graph and every collection in the project database."""
    if db.name == "_system":
        raise RuntimeError("refusing to reset the _system database")
    for g in db.graphs():           # including AWSAccessGraph, left by older versions of this repo
        db.delete_graph(g["name"])
    dropped = []
    for col in db.collections():
        if not col["system"]:
            db.delete_collection(col["name"])
            dropped.append(col["name"])
    return dropped
