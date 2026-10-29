"""Step 2: data.

Builds a synthetic AWS estate as RDF instance data. Every class, relationship and attribute
comes from the ontology profile, and every statement is checked against the ontology's
domain and range as it is written (see :class:`~awsgraph.ontology.DataBuilder`).

The estate has two accounts (dev and prod) and six teams. The background population is
deliberately well behaved: teams only reach their own data, public workloads only reach
public or internal data, and nothing crosses environments. The reference scenarios
(:mod:`awsgraph.scenarios`) then add the risky patterns, so the queries find exactly those.

    python -m awsgraph generate            # writes build/data.ttl
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph

from . import scenarios
from .estate import Account, Estate, Statement
from .ontology import ROOT, Ontology

TEAMS = ["app-team", "web-team", "platform-team", "security-team", "integration-team", "data-team"]


@dataclass(frozen=True)
class Size:
    users_per_team: int = 3
    roles_per_team: int = 3
    buckets_per_team: int = 3
    tables_per_team: int = 1
    instances_per_team: int = 2
    functions_per_team: int = 1


SIZES = {"demo": Size()}


def _team_stores(e: Estate, rng: random.Random, acct: Account, team: str, size: Size) -> dict[str, list[str]]:
    env = acct.environment
    key = e.kms_key(f"{team}-{env}-key", acct, team=team)
    stores: dict[str, list[str]] = {"sensitive": [], "internal": [], "public": [], "tables": []}
    for i in range(1, size.buckets_per_team + 1):
        cls = "internal" if i == 1 else rng.choice(["internal", "confidential", "confidential"])
        name = f"{team}-{env}-{['logs', 'records', 'reports', 'exports', 'uploads'][i - 1]}"
        e.bucket(name, acct, cls, team=team, key=key if cls != "internal" else None)
        stores["internal" if cls == "internal" else "sensitive"].append(f"arn:aws:s3:::{name}")
    if team == "web-team":
        name = f"web-team-{env}-public-site"
        e.bucket(name, acct, "public", team=team, public=True)
        stores["public"].append(f"arn:aws:s3:::{name}")
    for i in range(1, size.tables_per_team + 1):
        name = f"{team}-{env}-table-{i}"
        e.table(name, acct, rng.choice(["internal", "confidential"]), team=team, key=key)
        stores["tables"].append(e.arn(name))
    stores["key"] = [e.arn(f"{team}-{env}-key")]
    return stores


def _policies(e: Estate, acct: Account, team: str, stores: dict[str, list[str]]) -> dict[str, object]:
    env = acct.environment
    buckets = stores["sensitive"] + stores["internal"] + stores["public"]
    objs = [f"{b}/*" for b in buckets]
    read = e.managed_policy(f"{team}-{env}-read", [
        Statement(["s3:GetObject", "s3:ListBucket"], buckets + objs),
        Statement(["dynamodb:GetItem", "dynamodb:Query"], stores["tables"]),
        Statement(["kms:Decrypt"], stores["key"]),
    ], acct, team=team)
    write = e.managed_policy(f"{team}-{env}-write", [
        Statement(["s3:PutObject", "s3:GetObject"], objs),
        Statement(["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"], stores["tables"]),
        Statement(["kms:Decrypt", "kms:GenerateDataKey"], stores["key"]),
    ], acct, team=team)
    low = stores["internal"] + stores["public"]
    workload = e.managed_policy(f"{team}-{env}-workload", [
        Statement(["s3:GetObject"], [f"{b}/*" for b in low]),
        Statement(["s3:PutObject"], [f"{b}/*" for b in stores["internal"]]),
    ], acct, team=team)
    return {"read": read, "write": write, "workload": workload}


def _team(e: Estate, rng: random.Random, acct: Account, team: str, size: Size) -> None:
    env = acct.environment
    stores = _team_stores(e, rng, acct, team, size)
    pol = _policies(e, acct, team, stores)

    group = e.group(f"{team}-{env}-developers", acct, team=team)
    e.attach(group, pol["read"])
    for i in range(1, size.users_per_team + 1):
        user = e.user(f"{team}-{env}-user-{i}", acct, team=team)
        e.member_of(user, group)

    roles = []
    for i in range(1, size.roles_per_team + 1):
        role = e.role(f"{team}-{env}-service-role-{i}", acct, team=team, trusted_service="lambda.amazonaws.com")
        e.attach(role, pol["write"] if i == 1 else pol["read"])
        roles.append(role)
    for user in rng.sample(range(1, size.users_per_team + 1), k=1):
        e.can_assume(e.get(f"{team}-{env}-user-{user}"), roles[0])

    workload_role = e.role(f"{team}-{env}-workload-role", acct, team=team, trusted_service="ec2.amazonaws.com")
    e.attach(workload_role, pol["workload"])
    profile = e.instance_profile(f"{team}-{env}-workload-profile", acct, workload_role, team)
    for i in range(1, size.instances_per_team + 1):
        e.ec2_instance(f"{team}-{env}-instance-{i}", acct, profile, public=(team == "web-team" and i == 1),
                       team=team, instance_type=rng.choice(["t3.medium", "m6i.large", "c6i.xlarge"]))
    for i in range(1, size.functions_per_team + 1):
        e.lambda_function(f"{team}-{env}-function-{i}", acct, roles[-1], public=False, team=team)


def build(size: str = "demo", seed: int = 42) -> Estate:
    rng = random.Random(seed)
    e = Estate.new(Ontology())
    e.load_action_catalog()
    ou = e.organizational_unit("Workloads")
    dev = e.account("dev", "111122223333", "dev", ou)
    prod = e.account("prod", "444455556666", "prod", ou)

    for acct in (dev, prod):
        for team in TEAMS:
            _team(e, rng, acct, team, SIZES[size])
        admin = e.user(f"platform-{acct.environment}-admin", acct, team="platform-team")
        e.attach(admin, e.aws_managed_policy("AdministratorAccess", [Statement(["*"], ["*"])]))

    scenarios.plant(e, dev, prod)
    e.finish()
    return e


def write(path: Path | None = None, size: str = "demo", seed: int = 42) -> tuple[Path, Graph]:
    estate = build(size, seed)
    path = path or ROOT / "build" / "data.ttl"
    path.parent.mkdir(parents=True, exist_ok=True)
    estate.b.graph.serialize(path, format="turtle")
    return path, estate.b.graph
