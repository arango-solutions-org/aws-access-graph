# 4. Derived access

```bash
make derive
```

The data holds policies, not access. This step evaluates the policies inside ArangoDB and
writes the result as the ontology's derived terms:

- one edge collection per AWS access level: `canList`, `canRead`, `canWrite`,
  `canManagePermissions` and `canTag`;
- `hasEffectiveAccess`, their parent property, once for every principal and resource that has
  any of them. The ontology requires this pairing (REQ-045), so a query or tool that doesn't
  apply RDFS reasoning still finds the access. Its `levels` attribute lists the level edges it
  stands for;
- `isAdministrator` on every user and role.

The queries in the next step traverse the level edges.

Two AQL files do the work:

- [`aql/derive_effective_access.aql`](../aql/derive_effective_access.aql) writes the edges;
- [`aql/derive_administrators.aql`](../aql/derive_administrators.aql) sets the flag.

## The rules

1. **Which policies apply.** A user's or role's policies are the ones attached to it. A user
   also gets the policies attached to its groups.
2. **Matching.** A statement applies to an action and a resource when one of its action
   patterns matches the action (`*` and `?` wildcards, case-insensitive) and one of its
   resource patterns matches the resource's ARN (case-sensitive). An S3 object pattern
   (`arn:aws:s3:::bucket/*`) counts as the bucket.
3. **Service.** An action only applies to resources of its own service: `s3:` actions to
   buckets, `kms:` actions to keys.
4. **Account.** Identity policies only reach resources in the identity's own account.
   Cross-account access needs a resource-based policy, which isn't modelled. S3 ARNs carry no
   account ID, so the account is compared through the `environment` attribute.
5. **Deny and boundaries.** An explicit `Deny` beats any `Allow`. If a permission boundary is
   set, it must allow the action too.
6. **Access level.** Every allowed action has AWS's access level, and each level gives its own
   edge: List gives `canList`, Read `canRead`, Write `canWrite`, Permissions management
   `canManagePermissions` and Tagging `canTag`.
7. **Administrator.** `isAdministrator` is true when `*` on `*` is allowed, not denied, and not
   limited by a boundary.

Each edge records where it came from:

```json
{ "_from": "IAMUser/app-team-prod-user-1", "_to": "S3Bucket/app-team-prod-logs",
  "actions": ["s3:GetObject"], "policies": ["app-team-prod-read"],
  "viaGroups": ["app-team-prod-developers"], "derivedBy": "derive_effective_access.aql" }
```

## What it doesn't do

This is a small, readable evaluator for a reference implementation, not a replacement for IAM.
It doesn't evaluate:

- resource-based policies (bucket policies, KMS key policies)
- conditions
- service control policies
- session policies

It also doesn't evaluate role assumption from trust policies; see
[the modelling compromise](02-data.md#one-modelling-compromise).

On real data, take effective access from a tool built for it, such as IAM Access Analyzer or a
CIEM product, and write it into the same edge collections. The queries don't change.

## Checking the AQL

[`src/awsgraph/policy_eval.py`](../src/awsgraph/policy_eval.py) applies the same rules in Python,
without a database:

- **The unit tests** use it to check each scenario and control.
- **The end-to-end test** checks that the AQL produces exactly the same edges and
  administrators.

On the demo data, both give 439 `canList`, 589 `canRead`, 375 `canWrite`, 220
`canManagePermissions` and 219 `canTag` edges, paired by 670 `hasEffectiveAccess` edges, and
three administrators: `prod-admin-role`, `platform-dev-admin` and `platform-prod-admin`. The
derivation takes about 6 seconds.

Next: [5. Queries](05-queries.md)
