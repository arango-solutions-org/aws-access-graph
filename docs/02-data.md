# 2. Data

```bash
make generate validate      # writes build/data.ttl, then checks it against the SHACL shapes
```

The generator builds a synthetic AWS estate as RDF: 1,326 individuals and 5,680 statements.
It's deterministic, so the same seed always gives the same data.

## Only what the ontology allows

All data goes through one class, `DataBuilder` in [`src/awsgraph/ontology.py`](../src/awsgraph/ontology.py).
It does three checks on every write:

- **One class per individual**, and it must be in the profile.
- **Every relationship fits the property's domain and range.** Linking an S3 bucket with
  `canAssumeRole` raises an error, because the domain is `IAMEntity`.
- **Every attribute has the right type.** `isPubliclyAccessible` must be a boolean.

It also refuses to write the derived properties (`canRead`, `isAdministrator` and so on). Those
only come from the derivation step.

[`src/awsgraph/estate.py`](../src/awsgraph/estate.py) sits on top and knows AWS conventions: ARN
formats per service, policy JSON, trust policies and tags. Both the background population and
the reference scenarios use it, so planted data looks exactly like generated data.

## Policies the way the ontology models them

Access is never written as a shortcut edge. Each grant is a real IAM policy, stored twice:

- as the JSON document AWS uses, in `policyDocument`;
- as structured data, policy → `hasStatement` → statement → `hasEffect` / `hasAction` /
  `hasStatementResource`.

Every action the policies can match is in the graph with its AWS access level: 700 actions for
IAM, STS, S3, DynamoDB, RDS, Secrets Manager and KMS, taken from AWS's Service Authorization
Reference (see [`tools/build_action_catalog.py`](../tools/build_action_catalog.py)).

## The estate

Two accounts, `dev` (`111122223333`) and `prod` (`444455556666`), with six teams in each. Each
team has a group of users, service roles, a workload role with an instance profile, EC2
instances, a Lambda function, three buckets, a DynamoDB table, a secret and a KMS key. The data
team also has an RDS warehouse. All IDs are AWS's documentation placeholders and all names are
fictional.

The background is deliberately well behaved. Teams reach only their own data, workloads reach
only internal or public data, and nothing crosses accounts. That way the queries return the
reference scenarios and nothing else.

## Reference scenarios

[`src/awsgraph/scenarios.py`](../src/awsgraph/scenarios.py) adds the patterns the queries are
meant to find. Each has a control that shouldn't be flagged.

| Pattern | Flagged | Control |
|---|---|---|
| Indirect exposure | `public-web-instance` → `web-role`, which can assume `app-role`, which reads `customer-data` | `private-app-instance` reaches the same data but isn't public |
| Public workload running as admin | `public-bastion-instance` → `prod-admin-role` | |
| Public function writing sensitive data | `public-webhook-function` → `webhook-role` → `customer-data` | |
| Environment bridge | `dev-deployer-role` (dev) can assume `prod-deployer-role`, which can assume `prod-admin-role` | `breakglass-user` reaches admin through an approved break-glass path |
| Permission-rewrite escalation | `etl-service-user` can assume `etl-pipeline-role` and change its policies | `analyst-user` only reads, through its own team's role |
| Ownership gaps | `migration-scratch` (no team), `archived-reports` (team retired) | buckets written only by their own team |
| Cross-team writes | `etl-pipeline-role` (data-team) writes `financial-exports` (app-team) | `app-role` writes it too, but app-team owns it |
| Permission boundary | | `contractor-user` has `s3:*`, but a boundary limits it to reading `static-assets` |
| Explicit deny | | `auditor-role` can read every bucket except `financial-exports` |

## Validation

`make validate` runs the ontology's own SHACL shapes over the data with pySHACL. The result is
0 violations. The 244 warnings are the ones the ontology marks as expected by design: policy
statements, trust policies and inline policies have no ARN in AWS, and trust policies carry
their principals in JSON rather than as statements (see the next section).

## One modelling compromise

The ontology has no property for the principal in a trust policy. "Who can assume this role" is
stored as the ontology's `canAssumeRole` relationship, and the trust policy's JSON lists the
same principals. The derivation step doesn't re-evaluate trust policies.

Next: [3. Schema and load](03-schema.md)
