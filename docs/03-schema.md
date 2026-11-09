# 3. Schema and load

```bash
make schema load
```

## Collections come from the ontology

[`src/awsgraph/schema.py`](../src/awsgraph/schema.py) turns the profile into an ArangoDB schema:

- **One vertex collection per class:** `IAMRole`, `S3Bucket`, `PolicyStatement` and so on (23).
- **One edge collection per relationship:** `canAssumeRole`, `hasRole`, `canRead` and so on (21).
- **A named graph, `DataGraph`.** Each edge definition comes from the property's domain
  and range, expanded down the class hierarchy. For example:

| Edge collection | From | To |
|---|---|---|
| `canAssumeRole` | `IAMRole`, `IAMUser` | `IAMRole` |
| `hasPolicyAttachment` | `IAMGroup`, `IAMRole`, `IAMUser` | the five policy classes |
| `hasInstanceProfile` | `EC2Instance` | `IAMInstanceProfile` |
| `hasExecutionRole` | every AWS resource class | `IAMRole` |
| `canRead` (domain and range inherited from `hasEffectiveAccess`) | every AWS resource class | every AWS resource class |

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

The class of each individual reaches PGT as an ArangoDB collection statement, not as `rdf:type`,
so PGT doesn't also write an instance-to-class edge into `DataGraph`. The load step adds that
link itself, as a `dataType` edge (see below).

## Three graphs: ontology, data, knowledge

`make schema` also loads the ontology itself with ArangoRDF. The ontology and the data share one
database but sit in separate named graphs, as in Arango's Risk Intelligence demo:

| Graph | Holds | For |
|---|---|---|
| `OntologyGraph` | The ontology as ArangoRDF loads it: `Class`, `Property`, `subClassOf`, `domain`, `range`, `subPropertyOf`, and `type` for the ontology's own `rdf:type` statements | Exploring the ontology on its own; [Q9](../aql/queries/q09_ontology_relationships_for_a_class.aql) |
| `DataGraph` | The 23 class collections and the relationship edges, asserted and derived | The access queries, Q1 to Q8 |
| `KnowledgeGraph` | Both of the above, plus a `dataType` edge from every instance to its class | Showing the data and the ontology together; [Q10](../aql/queries/q10_estate_by_category.aql), which counts instances up the class hierarchy |

`KnowledgeGraph` reuses the edge definitions of the other two, read back from them when it's
created, because a collection that's in more than one graph must have the same definition in each.

### Why instance to class is an edge

An instance could instead hold its class's `_id` as an attribute and look it up with
`DOCUMENT()`. Going from an instance up to its class and on up `subClassOf`, the two cost about
the same. The difference is going down: a class with many instances is a supernode, so a
traversal from a class to its instances, or one that passes through a class, fans out over all
of them. Q10 goes down, to count instances. At this size that doesn't matter, and the edge shows
up in the graph viewer. On a large estate, keep traversals from passing through `Class`, or
replace `dataType` with an attribute.

## What's in the database afterwards

| | Count |
|---|---|
| Instances (vertices in the 23 class collections) | 1,326 |
| Asserted relationships | 1,292 |
| Ontology classes / properties (`Class`, `Property`) | 194 / 277 |
| `type` edges (ontology only) | 490 |
| `dataType` edges (instance to class) | 1,326 |

Next: [4. Derived access](04-derive.md)
