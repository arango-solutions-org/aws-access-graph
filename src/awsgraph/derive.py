"""Step 5: derive effective access.

Clears the derived edges, then runs ``aql/derive_effective_access.aql`` and
``aql/derive_administrators.aql`` inside ArangoDB. The rules are documented in
:mod:`awsgraph.policy_eval`, which applies the same rules in Python for the tests.

    python -m awsgraph derive
"""

from __future__ import annotations

from arango.database import StandardDatabase

from .ontology import ROOT

AQL = ROOT / "aql"
DERIVED_EDGES = ["hasEffectiveAccess", "canList", "canRead", "canWrite", "canManagePermissions", "canTag"]


def derive(db: StandardDatabase) -> dict:
    for name in DERIVED_EDGES:
        db.collection(name).truncate()
    edges = next(db.aql.execute((AQL / "derive_effective_access.aql").read_text()))
    admins = {}
    for col in ("IAMUser", "IAMRole"):
        res = list(db.aql.execute((AQL / "derive_administrators.aql").read_text(), bind_vars={"@entities": col}))
        admins[col] = res[0] if res else {"administrators": 0, "total": 0}
    return {"edges": edges, "administrators": admins}
