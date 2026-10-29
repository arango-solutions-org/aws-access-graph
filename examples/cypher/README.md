# Cypher equivalents

If your team writes Cypher, the same graph answers the same questions. Collection names
become labels and edge collection names become relationship types, so the patterns map
directly. These are static examples: each Cypher query is shown with the AQL in
`aql/queries` that answers the same question.

## Q1: Internet-facing workloads running with an administrator role

```cypher
MATCH p = (w)-[:hasInstanceProfile|hasRole|hasExecutionRole*1..2]->(role:IAMRole)
WHERE (w:EC2Instance OR w:LambdaFunction)
  AND w.isPubliclyAccessible = true
  AND role.isAdministrator = true
RETURN w.label AS workload, role.label AS adminRole,
       [n IN nodes(p) | n.label] AS route
ORDER BY workload
```

AQL: [`q01_public_workloads_running_as_admin.aql`](../../aql/queries/q01_public_workloads_running_as_admin.aql)

## Q5: Every route from a user to a data store

```cypher
MATCH (u:IAMUser {arn: $userArn}), (s:S3Bucket {arn: $storeArn})
MATCH p = (u)-[:canAssumeRole*0..5]->(holder)-[grant:canRead|canWrite|canManagePermissions]->(s)
RETURN [n IN nodes(p) | n.label] AS route, type(grant) AS access, length(p) AS hops
ORDER BY hops
```

AQL: [`q05_why_can_this_user_reach_this_store.aql`](../../aql/queries/q05_why_can_this_user_reach_this_store.aql).
The AQL also works out which links appear on every route, which is the smallest fix.
