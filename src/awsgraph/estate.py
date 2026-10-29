"""AWS-shaped helpers on top of :class:`~awsgraph.ontology.DataBuilder`.

These know how AWS names things (ARN formats, policy JSON) and how the ontology models them
(policy -> statement -> effect / action / resource). Both the background generator and the
reference scenarios use them, so planted data looks exactly like generated data.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field

from rdflib import URIRef

from .ontology import ROOT, DataBuilder, Ontology, slug

REGION = "us-east-1"
ORG_ID = "o-exampleorg1"
MANAGEMENT_ACCOUNT = "123456789012"


def load_action_catalog() -> dict[str, str]:
    """Action name -> AWS access level, from data/action_access_levels.csv."""
    with (ROOT / "data" / "action_access_levels.csv").open() as f:
        return {row["action"]: row["accessLevel"] for row in csv.DictReader(f)}


@dataclass(frozen=True)
class Account:
    uri: URIRef
    id: str
    environment: str


@dataclass
class Statement:
    actions: list[str]
    resources: list[str]
    effect: str = "Allow"


@dataclass
class Estate:
    """Everything created so far, indexed for the generator and the tests."""

    builder: DataBuilder
    catalog: dict[str, str] = field(default_factory=load_action_catalog)
    accounts: dict[str, Account] = field(default_factory=dict)
    by_label: dict[str, URIRef] = field(default_factory=dict)
    _trust: dict[URIRef, tuple[URIRef, dict[str, list[str]]]] = field(default_factory=dict)

    @classmethod
    def new(cls, ontology: Ontology | None = None) -> Estate:
        return cls(builder=DataBuilder(ontology or Ontology()))

    # -- plumbing --------------------------------------------------------------

    @property
    def b(self) -> DataBuilder:
        return self.builder

    def _named(self, cls: str, label: str, **attrs: object) -> URIRef:
        if label in self.by_label:
            raise ValueError(f"duplicate label {label!r}")
        uri = self.b.individual(cls, slug(label), label, **attrs)
        self.by_label[label] = uri
        return uri

    def get(self, label: str) -> URIRef:
        return self.by_label[label]

    def tag(self, resource: URIRef, key: str, value: str) -> None:
        tag = self.b.individual("Tag", f"{slug(key)}.{slug(value)}", f"{key}={value}",
                                tagKey=key, tagValue=value)
        self.b.link(resource, "hasTag", tag)

    def _tags(self, uri: URIRef, team: str | None, tags: dict[str, str] | None) -> None:
        if team:
            self.tag(uri, self.b.ont.profile.tags["owner"], team)
        for k, v in (tags or {}).items():
            self.tag(uri, k, v)

    # -- organisation ----------------------------------------------------------

    def organizational_unit(self, name: str) -> URIRef:
        ou_id = "ou-" + hashlib.sha1(name.encode()).hexdigest()[:8]
        return self._named("OrganizationalUnit", name,
                           arn=f"arn:aws:organizations::{MANAGEMENT_ACCOUNT}:ou/{ORG_ID}/{ou_id}")

    def account(self, name: str, account_id: str, environment: str, ou: URIRef) -> Account:
        uri = self._named("AWSAccount", name, environment=environment,
                          arn=f"arn:aws:organizations::{MANAGEMENT_ACCOUNT}:account/{ORG_ID}/{account_id}")
        self.b.link(uri, "belongsToOrganizationalUnit", ou)
        acct = Account(uri, account_id, environment)
        self.accounts[name] = acct
        return acct

    # -- identities --------------------------------------------------------------

    def user(self, name: str, acct: Account, team: str | None = None,
             tags: dict[str, str] | None = None) -> URIRef:
        uri = self._named("IAMUser", name, arn=f"arn:aws:iam::{acct.id}:user/{name}",
                          environment=acct.environment)
        self._tags(uri, team, tags)
        return uri

    def group(self, name: str, acct: Account, team: str | None = None) -> URIRef:
        uri = self._named("IAMGroup", name, arn=f"arn:aws:iam::{acct.id}:group/{name}",
                          environment=acct.environment)
        self._tags(uri, team, None)
        return uri

    def role(self, name: str, acct: Account, team: str | None = None, trusted_service: str | None = None,
             tags: dict[str, str] | None = None) -> URIRef:
        uri = self._named("IAMRole", name, arn=f"arn:aws:iam::{acct.id}:role/{name}",
                          environment=acct.environment, maxSessionDuration=3600)
        self._tags(uri, team, tags)
        trust = self._named("IAMTrustPolicy", f"{name}-trust")
        self.b.link(uri, "hasTrustRelationship", trust)
        self._trust[uri] = (trust, {"Service": [trusted_service]} if trusted_service else {})
        return uri

    def can_assume(self, principal: URIRef, role: URIRef) -> None:
        """The trust policy of ``role`` allows ``principal`` to assume it.

        The ontology has no property for a statement's principal, so trust is recorded as the
        ontology's ``canAssumeRole`` relationship rather than derived. The trust policy's JSON
        document lists the same principals.
        """
        self.b.link(principal, "canAssumeRole", role)
        principals = self._trust[role][1]
        arn = str(self.b.graph.value(principal, self.b.ns.arn))
        principals.setdefault("AWS", []).append(arn)

    def finish(self) -> None:
        """Write the trust policy documents once every principal is known."""
        for trust, principals in self._trust.values():
            statements = [{"Effect": "Allow",
                           "Principal": {k: v[0] if len(v) == 1 else v for k, v in principals.items()},
                           "Action": "sts:AssumeRole"}] if principals else []
            self.b.attr(trust, "policyDocument", json.dumps({"Version": "2012-10-17", "Statement": statements}))

    def member_of(self, user: URIRef, group: URIRef) -> None:
        self.b.link(user, "memberOf", group)

    def instance_profile(self, name: str, acct: Account, role: URIRef, team: str | None = None) -> URIRef:
        uri = self._named("IAMInstanceProfile", name, instanceProfileName=name,
                          arn=f"arn:aws:iam::{acct.id}:instance-profile/{name}")
        self._tags(uri, team, None)
        self.b.link(uri, "hasRole", role)
        return uri

    # -- policies --------------------------------------------------------------

    def _effect(self, name: str) -> URIRef:
        return self.b.individual("Effect", name.lower(), name)

    def load_action_catalog(self) -> None:
        """Add every action the catalog knows, with its AWS access level.

        Policies refer to actions with wildcards (``s3:Get*``, ``*``). The derivation step
        expands those against these concrete actions to find their access levels.
        """
        for name in self.catalog:
            self._action(name)

    def _action(self, name: str) -> URIRef:
        if "*" not in name and name not in self.catalog:
            raise ValueError(f"unknown action {name}: not in the Service Authorization Reference catalog")
        level = self.catalog.get(name)
        return self.b.individual("Action", name, name, accessLevel=level)

    def _resource(self, pattern: str) -> URIRef:
        key = slug(pattern)[:60] + "-" + hashlib.sha1(pattern.encode()).hexdigest()[:6]
        return self.b.individual("Resource", key, pattern)

    def _statements(self, policy: URIRef, policy_name: str, statements: list[Statement]) -> None:
        for i, st in enumerate(statements, 1):
            s = self.b.individual("PolicyStatement", f"{slug(policy_name)}.s{i}", f"{policy_name} #{i}")
            self.b.link(policy, "hasStatement", s)
            self.b.link(s, "hasEffect", self._effect(st.effect))
            for a in st.actions:
                self.b.link(s, "hasAction", self._action(a))
            for r in st.resources:
                self.b.link(s, "hasStatementResource", self._resource(r))

    @staticmethod
    def document(statements: list[Statement]) -> str:
        return json.dumps({"Version": "2012-10-17", "Statement": [
            {"Effect": s.effect,
             "Action": s.actions[0] if len(s.actions) == 1 else s.actions,
             "Resource": s.resources[0] if len(s.resources) == 1 else s.resources}
            for s in statements]})

    def managed_policy(self, name: str, statements: list[Statement], acct: Account | None = None,
                       team: str | None = None) -> URIRef:
        """A customer managed policy, or an AWS managed one when ``acct`` is None."""
        if acct is None:
            cls, arn = "AWSManagedPolicy", f"arn:aws:iam::aws:policy/{name}"
        else:
            cls, arn = "CustomerManagedPolicy", f"arn:aws:iam::{acct.id}:policy/{name}"
        uri = self._named(cls, name, arn=arn, policyDocument=self.document(statements))
        self._tags(uri, team, None)
        self._statements(uri, name, statements)
        return uri

    def aws_managed_policy(self, name: str, statements: list[Statement]) -> URIRef:
        """An AWS managed policy. These are shared, so asking twice returns the same one."""
        if name in self.by_label:
            return self.by_label[name]
        return self.managed_policy(name, statements)

    def inline_policy(self, owner: URIRef, name: str, statements: list[Statement]) -> URIRef:
        uri = self._named("InlinePolicy", name, policyDocument=self.document(statements))
        self._statements(uri, name, statements)
        self.b.link(owner, "hasPolicyAttachment", uri)
        return uri

    def boundary(self, name: str, acct: Account, statements: list[Statement]) -> URIRef:
        uri = self._named("IAMPermissionBoundary", name, arn=f"arn:aws:iam::{acct.id}:policy/{name}",
                          policyDocument=self.document(statements))
        self._statements(uri, name, statements)
        return uri

    def attach(self, identity: URIRef, policy: URIRef) -> None:
        self.b.link(identity, "hasPolicyAttachment", policy)

    def set_boundary(self, entity: URIRef, boundary: URIRef) -> None:
        self.b.link(entity, "hasPermissionBoundary", boundary)

    # -- compute -----------------------------------------------------------------

    def ec2_instance(self, name: str, acct: Account, profile: URIRef | None, public: bool,
                     team: str | None = None, instance_type: str = "t3.medium") -> URIRef:
        iid = "i-0" + hashlib.sha1(name.encode()).hexdigest()[:16]
        uri = self._named("EC2Instance", name, environment=acct.environment, isPubliclyAccessible=public,
                          instanceType=instance_type, arn=f"arn:aws:ec2:{REGION}:{acct.id}:instance/{iid}")
        self._tags(uri, team, None)
        if profile is not None:
            self.b.link(uri, "hasInstanceProfile", profile)
        return uri

    def lambda_function(self, name: str, acct: Account, role: URIRef, public: bool,
                        team: str | None = None) -> URIRef:
        uri = self._named("LambdaFunction", name, environment=acct.environment, isPubliclyAccessible=public,
                          arn=f"arn:aws:lambda:{REGION}:{acct.id}:function:{name}")
        self._tags(uri, team, None)
        self.b.link(uri, "hasExecutionRole", role)
        return uri

    # -- data --------------------------------------------------------------------

    def kms_key(self, name: str, acct: Account, team: str | None = None) -> URIRef:
        kid = hashlib.sha1(name.encode()).hexdigest()
        kid = f"{kid[:8]}-{kid[8:12]}-{kid[12:16]}-{kid[16:20]}-{kid[20:32]}"
        uri = self._named("KMSKey", name, environment=acct.environment,
                          arn=f"arn:aws:kms:{REGION}:{acct.id}:key/{kid}")
        self._tags(uri, team, None)
        return uri

    def _data_store(self, cls: str, name: str, acct: Account, arn: str, classification: str,
                    team: str | None, key: URIRef | None, public: bool, tags: dict[str, str] | None,
                    **attrs: object) -> URIRef:
        # S3 encrypts every new object by default, so a bucket is always encrypted; the other
        # stores are flagged as encrypted only when they use a KMS key.
        encrypted = cls == "S3Bucket" or key is not None
        uri = self._named(cls, name, arn=arn, environment=acct.environment, dataClassification=classification,
                          encrypted=encrypted, isPubliclyAccessible=public, **attrs)
        self._tags(uri, team, tags)
        if key is not None:
            self.b.link(uri, "encryptedWith", key)
        return uri

    def bucket(self, name: str, acct: Account, classification: str, team: str | None = None,
               key: URIRef | None = None, public: bool = False, tags: dict[str, str] | None = None) -> URIRef:
        return self._data_store("S3Bucket", name, acct, f"arn:aws:s3:::{name}", classification,
                                team, key, public, tags)

    def table(self, name: str, acct: Account, classification: str, team: str | None = None,
              key: URIRef | None = None) -> URIRef:
        return self._data_store("DynamoDBTable", name, acct,
                                f"arn:aws:dynamodb:{REGION}:{acct.id}:table/{name}",
                                classification, team, key, False, None, tableName=name)

    def database(self, name: str, acct: Account, classification: str, team: str | None = None,
                 key: URIRef | None = None, public: bool = False) -> URIRef:
        return self._data_store("RDSInstance", name, acct, f"arn:aws:rds:{REGION}:{acct.id}:db:{name}",
                                classification, team, key, public, None, engine="postgres")

    def secret(self, name: str, acct: Account, classification: str = "restricted", team: str | None = None,
               key: URIRef | None = None) -> URIRef:
        suffix = hashlib.sha1(name.encode()).hexdigest()[:6]
        return self._data_store("SecretsManagerSecret", name, acct,
                                f"arn:aws:secretsmanager:{REGION}:{acct.id}:secret:{name}-{suffix}",
                                classification, team, key, False, None, secretName=name)

    def arn(self, label: str) -> str:
        return str(self.b.graph.value(self.get(label), self.b.ns.arn))
