"""A reference implementation of the access derivation, in Python.

``aql/derive_effective_access.aql`` does this inside ArangoDB. This module applies the same
rules to the generated RDF, without a database. The tests use it to check the AQL, and
``docs/04-derive.md`` uses it to explain the rules.

The rules (deliberately simple; this is not a complete IAM evaluator):

1. A user's or role's policies are the ones attached to it, plus, for a user, the ones
   attached to its groups.
2. A statement applies to an (action, resource) pair when one of its action patterns matches
   the action (``*`` and ``?`` wildcards, case-insensitive) and one of its resource patterns
   matches the resource's ARN (case-sensitive). An S3 object pattern (``arn:aws:s3:::bucket/*``) counts as the
   bucket.
3. An action only applies to resources of its own service (``s3:`` actions to S3 buckets).
4. Identity policies only reach resources in the identity's own account. Cross-account
   access needs a resource-based policy, which isn't modelled. The demo has one account per
   environment, and S3 ARNs carry no account ID, so the account is compared through the
   ``environment`` attribute.
5. An explicit ``Deny`` beats any ``Allow``. A permission boundary, if set, must also allow.
6. Each allowed action has AWS's access level. Read gives ``canRead``, Write gives
   ``canWrite`` and Permissions management gives ``canManagePermissions``. List and Tagging
   are left out.
7. ``isAdministrator`` is true when ``*`` on ``*`` is allowed and not denied.

Not evaluated: resource-based policies, conditions, SCPs, session policies, and role
assumption (the graph models that as ``canAssumeRole`` and the queries traverse it).
"""

from __future__ import annotations

import fnmatch
from collections import defaultdict
from dataclasses import dataclass, field

from rdflib import RDF, RDFS, Graph, Namespace, URIRef

LEVEL_EDGE = {"Read": "canRead", "Write": "canWrite", "Permissions management": "canManagePermissions"}
TARGET_CLASSES = ["S3Bucket", "DynamoDBTable", "RDSInstance", "SecretsManagerSecret", "KMSKey", "IAMRole"]


@dataclass
class Stmt:
    effect: str
    actions: list[str]
    resources: list[str]
    label: str
    policy: str
    via: str | None = None


@dataclass
class Result:
    edges: dict[tuple[str, str, str], dict] = field(default_factory=dict)   # (edge, from, to) -> provenance
    admins: set[str] = field(default_factory=set)


def _glob(pattern: str, value: str) -> bool:
    """Action names match case-insensitively."""
    return fnmatch.fnmatchcase(value.lower(), pattern.lower())


def service_of(arn: str) -> str:
    return arn.split(":")[2]


def resource_matches(pattern: str, arn: str) -> bool:
    if pattern == "*":
        return True
    if service_of(arn) == "s3" and pattern.startswith("arn:aws:s3:::"):
        pattern = pattern.split("/", 1)[0]
    return fnmatch.fnmatchcase(arn, pattern)   # ARNs match case-sensitively


def derive(g: Graph, ns: Namespace) -> Result:
    label = lambda u: str(g.value(u, RDFS.label))  # noqa: E731

    def statements(policy: URIRef, via: str | None) -> list[Stmt]:
        out = []
        for s in g.objects(policy, ns.hasStatement):
            out.append(Stmt(
                effect=label(g.value(s, ns.hasEffect)),
                actions=[label(a) for a in g.objects(s, ns.hasAction)],
                resources=[label(r) for r in g.objects(s, ns.hasStatementResource)],
                label=label(s), policy=label(policy), via=via))
        return out

    catalog = defaultdict(list)   # service -> [(action, level)]
    for a in g.subjects(RDF.type, ns.Action):
        level = g.value(a, ns.accessLevel)
        if level is not None:
            name = label(a)
            catalog[name.split(":")[0]].append((name, str(level)))

    targets = []
    for cls in TARGET_CLASSES:
        for t in g.subjects(RDF.type, ns[cls]):
            arn = str(g.value(t, ns.arn))
            targets.append((t, arn, str(g.value(t, ns.environment)), service_of(arn)))

    result = Result()
    entities = list(g.subjects(RDF.type, ns.IAMUser)) + list(g.subjects(RDF.type, ns.IAMRole))
    for ent in entities:
        env = str(g.value(ent, ns.environment))
        own = [st for p in g.objects(ent, ns.hasPolicyAttachment) for st in statements(p, None)]
        for grp in g.objects(ent, ns.memberOf):
            own += [st for p in g.objects(grp, ns.hasPolicyAttachment) for st in statements(p, label(grp))]
        boundary = [st for b in g.objects(ent, ns.hasPermissionBoundary) for st in statements(b, None)]
        has_boundary = bool(list(g.objects(ent, ns.hasPermissionBoundary)))

        def allowed(stmts: list[Stmt], action: str, arn: str) -> list[Stmt]:
            return [st for st in stmts if st.effect == "Allow"
                    and any(_glob(p, action) for p in st.actions)
                    and any(resource_matches(r, arn) for r in st.resources)]

        def denied(action: str, arn: str, stmts: list[Stmt] = own + boundary) -> bool:
            return any(st.effect == "Deny" and any(_glob(p, action) for p in st.actions)
                       and any(resource_matches(r, arn) for r in st.resources) for st in stmts)

        for t, arn, t_env, svc in targets:
            if t_env != env:
                continue
            for action, level in catalog.get(svc, []):
                edge = LEVEL_EDGE.get(level)
                if edge is None:
                    continue
                grants = allowed(own, action, arn)
                if not grants or denied(action, arn):
                    continue
                if has_boundary and not allowed(boundary, action, arn):
                    continue
                prov = result.edges.setdefault((edge, label(ent), label(t)),
                                               {"actions": set(), "policies": set(), "via": set()})
                prov["actions"].add(action)
                for st in grants:
                    prov["policies"].add(st.policy)
                    if st.via:
                        prov["via"].add(st.via)

        star = [st for st in own if st.effect == "Allow" and "*" in st.actions and "*" in st.resources]
        star_denied = any(st.effect == "Deny" and "*" in st.actions and "*" in st.resources for st in own + boundary)
        boundary_ok = not has_boundary or any("*" in st.actions and "*" in st.resources
                                              for st in boundary if st.effect == "Allow")
        if star and not star_denied and boundary_ok:
            result.admins.add(label(ent))
    return result
