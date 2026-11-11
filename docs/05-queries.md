# 5. Queries

```bash
make queries            # all of them
python -m awsgraph queries q05
```

Each file in [`aql/queries`](../aql/queries) is one question. Its header comment has the bind
parameters as JSON, which the runner uses. The results on the demo data are in
[RESULTS.md](RESULTS.md), and CI checks them.

| # | Question | Pattern |
|---|---|---|
| [Q1](../aql/queries/q01_public_workloads_running_as_admin.aql) | Which internet-facing workloads run with an administrator role? | 1–2 hops from workload to role |
| [Q2](../aql/queries/q02_public_workloads_reaching_sensitive_data.aql) | Which internet-facing workloads can reach sensitive data, through any chain of roles? | variable-depth traversal, ends at a grant |
| [Q3](../aql/queries/q03_blast_radius.aql) | What can this user or role reach? | blast radius |
| [Q4](../aql/queries/q04_who_can_reach_this_store.aql) | Who can reach this data store? | reverse blast radius |
| [Q5](../aql/queries/q05_why_can_this_user_reach_this_store.aql) | Why can this user reach this store, and which link do all routes share? | `K_PATHS`, then intersect |
| [Q6](../aql/queries/q06_escalation_to_admin.aql) | Which users can escalate to administrator? | traversal with two stop conditions |
| [Q7](../aql/queries/q07_dev_to_prod_bridges.aql) | Which dev identities can reach prod roles, and through which trust link? | first edge that crosses environments |
| [Q8](../aql/queries/q08_ownership_gaps.aql) | Which sensitive buckets have no owner, or can be changed by another team? | tags as shared vertices |
| [Q9](../aql/queries/q09_ontology_relationships_for_a_class.aql) | What does the ontology say an IAM role can have? | the ontology as a schema |
| [Q10](../aql/queries/q10_estate_by_category.aql) | How much of each kind of resource is there? | instances rolled up the class hierarchy |

## Conventions

- **A grant ends a route.** Permission on a role (`canManagePermissions` on `etl-pipeline-role`)
  is not the same as acting as it. Traversals `PRUNE` at the first `canRead`, `canWrite` or
  `canManagePermissions` edge, and only `canAssumeRole` and the workload links carry a route
  further.
- **Name the edges.** Each traversal lists the edge collections it may follow, rather than using
  the whole named graph. The `WITH` line lists the vertex collections, which a cluster needs.
- **Start from an index.** Each query starts from an ARN, a flag or a classification, all of
  which are indexed.
- **Admin routes are separate.** An administrator role reaches everything. Q2 leaves those
  routes out unless `throughAdminRoles` is true, because Q1 already reports them. Q8 leaves
  administrators out because Q6 covers them.

## Worked example: the smallest fix (Q5)

`dev-user` is a developer in the dev account. Q5 finds every route from it to
`financial-exports`, then keeps the links that appear on every route:

```
dev-user -> dev-deployer-role -> prod-deployer-role -> app-role        -> financial-exports   canWrite
dev-user -> dev-deployer-role -> prod-deployer-role -> prod-admin-role -> financial-exports   canRead, canWrite, canManagePermissions

on every route:  dev-user -> dev-deployer-role
                 dev-deployer-role -> prod-deployer-role
```

Removing the trust from `dev-deployer-role` to `prod-deployer-role` closes both routes. It's the
same link Q7 reports as the bridge between environments.

## In the Arango web UI

```bash
make ui
```

This saves the queries in the database, so they can be run, and their routes drawn, from the
web UI (on the local install, [https://127.0.0.1:8529/ui/](https://127.0.0.1:8529/ui/)):

- **Query editor, saved queries.** The ten questions above, with their default bind
  parameters. They return tables, the same as `make queries`.
- **Graph Visualizer, Queries panel.** A graph version of each question, from
  [`aql/visualizer`](../aql/visualizer), which returns the routes behind the answer as paths
  so the visualizer can draw them. Q1 to Q8 are on `DataGraph`, Q9 on `OntologyGraph` and Q10
  on `KnowledgeGraph`. Open the graph, then pick the query from the Queries panel. Where a
  question has several routes to the same answer, the graph version draws the shortest one,
  except Q5, which draws every route.

Each graph version has the same header and bind parameters as its question (Q10 adds
`instancesPerClass`), plus a `// graph:` line naming its graph. The end-to-end test checks that each returns paths whose
edges are all in that graph.

The saved documents all have keys starting `awsgraph_`. Running `make ui` again replaces them,
and leaves alone any queries saved by hand in the UI. `make all` runs it as the last step.

## SPARQL and Cypher

- **[`examples/sparql`](../examples/sparql)** runs SPARQL over the ontology and the generated Turtle with rdflib.
  `01` asks the same question as Q9 and returns the same six properties; `tests/test_sparql.py` checks that they agree.
- **[`examples/cypher`](../examples/cypher)** shows Q1 and Q5 in Cypher next to the AQL. The
  collection names become labels and relationship types, so the patterns map one to one.
