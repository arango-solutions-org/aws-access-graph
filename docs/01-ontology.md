# 1. Ontology

Everything in this repo starts from the open [AWS ontology](https://github.com/arango-solutions-org/aws-ontology).
It was written from AWS's public documentation, it's MIT-licensed, and it defines AWS resource
types as OWL classes and the relationships between them as properties. The repo uses it as the
contract for the graph. The data generator, the database schema and the queries all take
their names and their rules from it.

## What's pinned

`ontology/vendor/` holds a copy of `aws.ttl` (the ontology) and `aws.shapes.ttl` (its SHACL
validation rules). `SOURCE.md` records the exact commits and a checksum, and
`tests/test_ontology.py` fails if either file changes, so an ontology upgrade is always a
deliberate step.

Two additions to the ontology were made for this project and proposed upstream:

| Added | Why the blueprint needs it |
|---|---|
| `hasExecutionRole`, `hasInstanceProfile` | How a Lambda function or EC2 instance gets its permissions |
| `Tag`, `hasTag`, `tagKey`, `tagValue` | Ownership (`team=...`) and exceptions (`breakglass=approved`) |
| `accessLevel` on `Action` | AWS's own classification of every API action: List, Read, Write, Permissions management, Tagging |
| `isPubliclyAccessible` | Which workloads face the internet |
| `hasEffectiveAccess` → `canRead`, `canWrite`, `canManagePermissions` | The result of evaluating policies. Derived, not stored by AWS |
| `isAdministrator` | Derived, as above |

## The profile

The full ontology has 163 classes. This project uses 23 of them, listed in
[`ontology/profile.yaml`](../ontology/profile.yaml):

| Group | Classes |
|---|---|
| Organisation | `AWSAccount`, `OrganizationalUnit` |
| Identity | `IAMUser`, `IAMGroup`, `IAMRole`, `IAMInstanceProfile` |
| Policy | `AWSManagedPolicy`, `CustomerManagedPolicy`, `InlinePolicy`, `IAMTrustPolicy`, `IAMPermissionBoundary`, `PolicyStatement`, `Action`, `Resource`, `Effect` |
| Compute | `EC2Instance`, `LambdaFunction` |
| Data | `S3Bucket`, `DynamoDBTable`, `RDSInstance`, `SecretsManagerSecret` |
| Security | `KMSKey` |
| Metadata | `Tag` |

The profile also says which relationships the generator may write and which ones only the
derivation step may write. `Ontology()` in [`src/awsgraph/ontology.py`](../src/awsgraph/ontology.py)
loads both files and refuses to start if anything in the profile isn't in the ontology.

## Why the class hierarchy matters

Properties are defined on general classes. `canAssumeRole` has the domain `IAMEntity`, which
covers users and roles. `hasPolicyAttachment` has the domain `IAMIdentity`, which also covers
groups. The code walks `rdfs:subClassOf` to work out what each property can connect, so the
data and the schema follow the ontology's hierarchy rather than a hand-written list.

```
IAMRole ⊂ IAMEntity ⊂ IAMIdentity ⊂ IdentityResource ⊂ AWSResource
IAMUser ⊂ IAMEntity
IAMGroup ⊂ IAMIdentity
```

You can ask the ontology directly what an IAM role can have. In SPARQL, over the Turtle file:

```bash
python -m awsgraph.sparql examples/sparql/01_relationships_between_classes.rq
```

The same question in AQL, once the ontology is loaded into ArangoDB, is
[Q9](../aql/queries/q09_ontology_relationships_for_a_class.aql). Both return the same ten
properties. See [RESULTS.md](RESULTS.md#q9).

Next: [2. Data](02-data.md)
