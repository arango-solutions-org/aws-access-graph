# 3. Schema and load

```bash
make schema load
```

## Collections come from the ontology

[`src/awsgraph/schema.py`](../src/awsgraph/schema.py) turns the profile into an ArangoDB schema:

- **One vertex collection per class:** `IAMRole`, `S3Bucket`, `PolicyStatement` and so on (23).
- **One edge collection per relationship:** `canAssumeRole`, `hasRole`, `canRead` and so on (18).
- **A named graph, `AWSAccessGraph`.** Each edge definition comes from the property's domain
  and range, expanded down the class hierarchy. For example:

| Edge collection | From | To |
|---|---|---|
| `canAssumeRole` | `IAMRole`, `IAMUser` | `IAMRole` |
| `hasPolicyAttachment` | `IAMGroup`, `IAMRole`, `IAMUser` | the five policy classes |
| `hasInstanceProfile` | `EC2Instance` | `IAMInstanceProfile` |
| `hasExecutionRole` | `EC2Instance`, `LambdaFunction` | `IAMRole` |

The names are the ontology's own, so a query reads like the ontology. That breaks the usual
snake_case convention on purpose.

### Why one collection per type

A traversal over a specific edge collection only ever sees that kind of relationship. The
queries list exactly the edges a route may follow, for example `hasInstanceProfile, hasRole,
canAssumeRole`, so they can't wander into unrelated parts of the graph and need no per-hop type
filter. Using one collection per type can speed up queries considerably in ArangoDB. In earlier
testing on a large access graph, multi-hop traversals ran about twice as fast as with a single
labelled collection.

### Indexes

| Index | On | For |
|---|---|---|
| `arn`, unique | every AWS resource | looking up the start of a query by ARN |
| `environment` | every AWS resource | Q7 and the derivation's same-account rule |
| `isPubliclyAccessible` | compute and data stores | Q1, Q2 |
| `dataClassification` | data stores and secrets | Q2, Q3, Q8 |
| `tagKey`, `tagValue`, unique | `Tag` | ownership lookups |
| `label`, unique; `accessLevel` | `Action` | the derivation |

Edge collections get ArangoDB's built-in `_from` and `_to` indexes. At this scale that's
enough. On large estates, add vertex-centric indexes to the busiest edge collections.

## Loading with ArangoRDF

[`src/awsgraph/load.py`](../src/awsgraph/load.py) loads the Turtle file with
[ArangoRDF](https://github.com/ArangoDB-Community/ArangoRDF)'s Property Graph Transformation
(PGT):

- each individual goes into the collection named after its class;
- each relationship becomes an edge in the collection named after the property;
- each attribute becomes a document field.

Document keys are the readable keys the generator assigned (`IAMRole/app-role`,
`Action/s3:GetObject`) rather than hashes, so results and `_id`s are easy to read.

`make schema` also loads the ontology itself into the same graph: `Class`, `Property`,
`subClassOf`, `domain`, `range` and `subPropertyOf`. ArangoRDF links every instance to its class
with a `type` edge. That's why the ontology and the data share one named graph: an edge
collection can only have one definition. It's also what makes [Q10](../aql/queries/q10_estate_by_category.aql)
possible, which counts instances up the class hierarchy.

## What's in the database afterwards

| | Count |
|---|---|
| Instances (vertices in the 23 class collections) | 1,326 |
| Asserted relationships | 1,292 |
| Ontology classes / properties (`Class`, `Property`) | 194 / 279 |
| `type` edges (instance and ontology) | about 1,800 |

Next: [4. Derived access](04-derive.md)
