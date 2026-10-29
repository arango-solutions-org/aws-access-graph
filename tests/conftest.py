import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(scope="session")
def ontology():
    from awsgraph.ontology import Ontology
    return Ontology()


@pytest.fixture(scope="session")
def estate():
    from awsgraph.generate import build
    return build()


@pytest.fixture(scope="session")
def derived(estate):
    from awsgraph.policy_eval import derive
    return derive(estate.b.graph, estate.b.ns)
