# Results

Output of every query on the demo data (`make all`, seed 42), with the bind parameters in each
query file. These are generated from `tests/expected/`, which the end-to-end test checks against
a live ArangoDB in CI. Don't edit this page by hand: run `python tools/render_results.py`.

<a id="q1"></a>
## Q1. Which internet-facing workloads run with an administrator role?

[`q01_public_workloads_running_as_admin.aql`](../aql/queries/q01_public_workloads_running_as_admin.aql) · bind: `{}` · 1 row

| workload | type | adminRole | route |
|---|---|---|---|
| public-bastion-instance | EC2Instance | prod-admin-role | public-bastion-instance -> bastion-instance-profile -> prod-admin-role |

<a id="q2"></a>
## Q2. Which internet-facing workloads can reach sensitive data, through any chain of roles?

[`q02_public_workloads_reaching_sensitive_data.aql`](../aql/queries/q02_public_workloads_reaching_sensitive_data.aql) · bind: `{"maxDepth": 6, "sensitive": ["confidential", "restricted"], "throughAdminRoles": false}` · 3 rows

| workload | store | storeType | access | hops | route |
|---|---|---|---|---|---|
| public-web-instance | customer-data | S3Bucket | canRead | 4 | public-web-instance -> web-instance-profile -> web-role -> app-role -> customer-data |
| public-web-instance | financial-exports | S3Bucket | canWrite | 4 | public-web-instance -> web-instance-profile -> web-role -> app-role -> financial-exports |
| public-webhook-function | customer-data | S3Bucket | canWrite | 2 | public-webhook-function -> webhook-role -> customer-data |

<a id="q3"></a>
## Q3. What can this user or role reach, including every role it can assume? (blast radius)

[`q03_blast_radius.aql`](../aql/queries/q03_blast_radius.aql) · bind: `{"principalArn": "arn:aws:iam::111122223333:user/dev-user", "maxDepth": 6, "classifications": ["confidential", "restricted"]}` · 21 rows

| resource | type | classification | access | via | hops |
|---|---|---|---|---|---|
| platform-team-prod-table-1 | DynamoDBTable | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| security-team-prod-table-1 | DynamoDBTable | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| web-team-prod-table-1 | DynamoDBTable | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| data-team-prod-warehouse | RDSInstance | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| analytics-events | S3Bucket | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| app-team-prod-records | S3Bucket | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| archived-reports | S3Bucket | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| customer-data | S3Bucket | confidential | canManagePermissions, canRead, canWrite | app-role, prod-admin-role | 4 |
| data-team-prod-records | S3Bucket | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| financial-exports | S3Bucket | restricted | canManagePermissions, canRead, canWrite | app-role, prod-admin-role | 4 |
| integration-team-prod-records | S3Bucket | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| migration-scratch | S3Bucket | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| platform-team-prod-reports | S3Bucket | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| security-team-prod-reports | S3Bucket | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| web-team-prod-records | S3Bucket | confidential | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| app-team-prod-credentials | SecretsManagerSecret | restricted | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| data-team-prod-credentials | SecretsManagerSecret | restricted | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| integration-team-prod-credentials | SecretsManagerSecret | restricted | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| platform-team-prod-credentials | SecretsManagerSecret | restricted | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| security-team-prod-credentials | SecretsManagerSecret | restricted | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |
| web-team-prod-credentials | SecretsManagerSecret | restricted | canManagePermissions, canRead, canWrite | prod-admin-role | 4 |

<a id="q4"></a>
## Q4. Which users, roles and workloads can reach this data store? (reverse blast radius)

[`q04_who_can_reach_this_store.aql`](../aql/queries/q04_who_can_reach_this_store.aql) · bind: `{"storeArn": "arn:aws:s3:::financial-exports", "maxDepth": 6}` · 14 rows

| who | type | hops | access |
|---|---|---|---|
| app-role | IAMRole | 1 | canWrite |
| etl-pipeline-role | IAMRole | 1 | canWrite |
| prod-admin-role | IAMRole | 1 | canManagePermissions, canRead, canWrite |
| platform-prod-admin | IAMUser | 1 | canManagePermissions, canRead, canWrite |
| prod-deployer-role | IAMRole | 2 | canManagePermissions, canRead, canWrite |
| web-role | IAMRole | 2 | canWrite |
| breakglass-user | IAMUser | 2 | canManagePermissions, canRead, canWrite |
| etl-service-user | IAMUser | 2 | canWrite |
| private-app-instance | EC2Instance | 3 | canWrite |
| public-bastion-instance | EC2Instance | 3 | canManagePermissions, canRead, canWrite |
| dev-deployer-role | IAMRole | 3 | canManagePermissions, canRead, canWrite |
| public-web-instance | EC2Instance | 4 | canWrite |
| ci-service-user | IAMUser | 4 | canManagePermissions, canRead, canWrite |
| dev-user | IAMUser | 4 | canManagePermissions, canRead, canWrite |

<a id="q5"></a>
## Q5. Why can this user reach this data store? Every route, and the links they all share

[`q05_why_can_this_user_reach_this_store.aql`](../aql/queries/q05_why_can_this_user_reach_this_store.aql) · bind: `{"userArn": "arn:aws:iam::111122223333:user/dev-user", "storeArn": "arn:aws:s3:::financial-exports", "maxDepth": 6}` · 1 row

| access | grantedBy | hops | route |
|---|---|---|---|
| canWrite | app-data-access | 4 | dev-user -> dev-deployer-role -> prod-deployer-role -> app-role -> financial-exports |
| canManagePermissions, canRead, canWrite | AdministratorAccess | 4 | dev-user -> dev-deployer-role -> prod-deployer-role -> prod-admin-role -> financial-exports |

**On every route:** `dev-user -> dev-deployer-role`, `dev-deployer-role -> prod-deployer-role`

<a id="q6"></a>
## Q6. Which users can escalate to administrator, by assuming an admin role or by changing a role's permissions?

[`q06_escalation_to_admin.aql`](../aql/queries/q06_escalation_to_admin.aql) · bind: `{"maxDepth": 6}` · 3 rows

| user | method | target | targetIsAdmin | hops | route |
|---|---|---|---|---|---|
| etl-service-user | MANAGE_ROLE_PERMISSIONS | etl-pipeline-role | no | 1 | etl-service-user -> etl-pipeline-role |
| ci-service-user | ASSUME_ADMIN_ROLE | prod-admin-role | yes | 3 | ci-service-user -> dev-deployer-role -> prod-deployer-role -> prod-admin-role |
| dev-user | ASSUME_ADMIN_ROLE | prod-admin-role | yes | 3 | dev-user -> dev-deployer-role -> prod-deployer-role -> prod-admin-role |

<a id="q7"></a>
## Q7. Which development identities can reach production roles, and through which trust link?

[`q07_dev_to_prod_bridges.aql`](../aql/queries/q07_dev_to_prod_bridges.aql) · bind: `{"sourceEnv": "dev", "targetEnv": "prod", "maxDepth": 6}` · 3 rows

| principal | type | productionRoles | canReachAdmin | bridges |
|---|---|---|---|---|
| ci-service-user | IAMUser | app-role, prod-admin-role, prod-deployer-role | yes | dev-deployer-role -> prod-deployer-role |
| dev-deployer-role | IAMRole | app-role, prod-admin-role, prod-deployer-role | yes | dev-deployer-role -> prod-deployer-role |
| dev-user | IAMUser | app-role, prod-admin-role, prod-deployer-role | yes | dev-deployer-role -> prod-deployer-role |

<a id="q8"></a>
## Q8. Which sensitive buckets have no accountable team, or can be changed by another team?

[`q08_ownership_gaps.aql`](../aql/queries/q08_ownership_gaps.aql) · bind: `{"sensitive": ["confidential", "restricted"], "activeTeams": ["app-team", "web-team", "platform-team", "security-team", "integration-team", "data-team"]}` · 4 rows

| bucket | ownerTeam | ownerStatus | outsideWriters |
|---|---|---|---|
| customer-data | app-team | ACTIVE | webhook-role (integration-team) |
| financial-exports | app-team | ACTIVE | etl-pipeline-role (data-team) |
| archived-reports | retired-team | INACTIVE_TEAM | etl-service-user (data-team, has an inline policy) |
| migration-scratch |  | NO_OWNER | etl-pipeline-role (data-team) |

<a id="q9"></a>
## Q9. What does the ontology say an IAM role can have? (the ontology as a queryable schema)

[`q09_ontology_relationships_for_a_class.aql`](../aql/queries/q09_ontology_relationships_for_a_class.aql) · bind: `{"fromClass": "IAMRole", "generic": ["IdentityResource", "AWSResource", "Entity"]}` · 6 rows

| property | domain | range | parent |
|---|---|---|---|
| canAssumeRole | IAMEntity | IAMRole |  |
| hasPermissionBoundary | IAMEntity | IAMPermissionBoundary |  |
| hasPolicyAttachment | IAMIdentity | IAMPolicy |  |
| hasTrustRelationship | IAMRole | IAMTrustPolicy |  |
| isAdministrator | IAMEntity | boolean |  |
| maxSessionDuration | IAMRole | integer |  |

<a id="q10"></a>
## Q10. How much of each kind of resource is in the estate? (instances rolled up the class hierarchy)

[`q10_estate_by_category.aql`](../aql/queries/q10_estate_by_category.aql) · bind: `{"categories": ["ComputeResource", "StorageResource", "DatabaseResource", "SecurityResource", "IdentityResource"]}` · 5 rows

| category | instances | by class |
|---|---|---|
| IdentityResource | 362 | PolicyStatement 127, IAMRole 57, IAMTrustPolicy 57, IAMUser 44, CustomerManagedPolicy 43, IAMInstanceProfile 15, IAMGroup 12, InlinePolicy 3, AWSManagedPolicy 2, IAMPermissionBoundary 1, OrganizationalUnit 1 |
| StorageResource | 45 | S3Bucket 45 |
| ComputeResource | 40 | EC2Instance 27, LambdaFunction 13 |
| SecurityResource | 25 | KMSKey 13, SecretsManagerSecret 12 |
| DatabaseResource | 14 | DynamoDBTable 12, RDSInstance 2 |
