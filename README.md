# AWS identity and access management (IAM) graph blueprint

A reference implementation of an AWS identity and access management (IAM) graph on ArangoDB that starts from an open
ontology and works forward:

**ontology → schema → data → derived access → queries**

Each step is a small, readable module and a `make` target, so you can follow it in order:

| Step | What happens | Code | Run |
|---|---|---|---|
| [1. Ontology](docs/01-ontology.md) | Pin the open [AWS ontology](https://github.com/arango-solutions-org/aws-ontology) and pick the classes and properties this project uses | `ontology/`, `src/awsgraph/ontology.py` | |
| [2. Data](docs/02-data.md) | Generate a synthetic AWS estate as RDF. Every statement is checked against the ontology's domain and range, then the data is checked against its SHACL shapes | `generate.py`, `scenarios.py`, `validate.py` | `make generate validate` |
| [3. Schema](docs/03-schema.md) | One collection per class, one edge collection per relationship, a data graph built from domain and range, and indexes. The ontology is loaded into its own graph, and a knowledge graph combines the two | `schema.py` | `make schema` |
| [4. Load](docs/03-schema.md#loading-with-arangordf) | Load the data with [ArangoRDF](https://github.com/ArangoDB-Community/ArangoRDF) and link each instance to its class | `load.py` | `make load` |
| [5. Derive](docs/04-derive.md) | Evaluate IAM policies in AQL and write `hasEffectiveAccess`, one edge per access level (`canList`, `canRead`, `canWrite`, `canManagePermissions`, `canTag`) and `isAdministrator` | `aql/derive_*.aql` | `make derive` |
| [6. Query](docs/05-queries.md) | Eight security questions and two ontology questions in AQL, plus SPARQL and Cypher examples | `aql/queries/`, `examples/` | `make queries` |
| [7. Web UI](docs/05-queries.md#in-the-arango-web-ui) | Save the queries in the database for the query editor, and a graph version of each for the Graph Visualizer | `aql/visualizer/`, `ui.py` | `make ui` |

## Quick start

The demo runs on the local install of the Arango Contextual Data Platform. Install it first from
[arango.ai/arango-developer-edition](https://arango.ai/arango-developer-edition/). It runs a
small Kubernetes cluster on your machine, using kind (Kubernetes in Docker), so Docker needs to
be running with at least 8 GB of memory. The installer sets up kind, helm and kubectl if you
don't have them. `make forward` uses kubectl to reach the database inside the cluster.

```bash
make forward                # in a second terminal, and leave it running: https://127.0.0.1:8529
```

```bash
git clone https://github.com/arango-solutions-org/aws-access-graph.git
cd aws-access-graph
python -m venv .venv && source .venv/bin/activate
make install
cp .env.example .env        # already set up for the local install (root / test)
make all
```

Then open [https://127.0.0.1:8529/ui/](https://127.0.0.1:8529/ui/). The ten questions are in the
query editor's saved queries, and their graph versions are in the Graph Visualizer's Queries
panel for `DataGraph`, `OntologyGraph` and `KnowledgeGraph` (see
[step 7](docs/05-queries.md#in-the-arango-web-ui)).

`make test` runs the unit tests (no database needed). `make e2e` runs the whole pipeline
against the database in `.env` and checks every query result against
[docs/RESULTS.md](docs/RESULTS.md). If you change the data or a query on purpose, `make expected`
re-records the results and re-renders that page.

If something fails to connect, the error says which of these it is:

- **Nothing is answering**: the port-forward has stopped. Run `make forward` again.
- **Certificate check failed**: `.env` is missing `ARANGO_VERIFY_SSL=false`. The local
  install's certificate is self-signed for its in-cluster names, not for 127.0.0.1.
- **User was refused**: `ARANGO_PASSWORD` doesn't match. The installer sets `root` / `test`;
  use your own if you've changed it.

To use another deployment instead, such as a managed one, change the settings in `.env`;
`.env.example` shows how.

## The questions

| # | Question |
|---|---|
| Q1 | Which internet-facing workloads run with an administrator role? |
| Q2 | Which internet-facing workloads can reach sensitive data, through any chain of roles? |
| Q3 | What can this user or role reach, including every role it can assume? |
| Q4 | Which users, roles and workloads can reach this data store? |
| Q5 | Why can this user reach this data store, and which link do all the routes share? |
| Q6 | Which users can escalate to administrator? |
| Q7 | Which development identities can reach production roles, and through which trust link? |
| Q8 | Which sensitive buckets have no accountable team, or can be changed by another team? |
| Q9 | What does the ontology say an IAM role can have? (the ontology, queried in ArangoDB) |
| Q10 | How much of each kind of resource is in the estate? (instances rolled up the class hierarchy) |

## What's in the data

Two AWS accounts (dev and prod) with six teams, each with users, groups, roles, workloads,
buckets, tables and KMS keys. The background population is well behaved: teams only reach
their own data, and nothing crosses environments. The reference scenarios in
`src/awsgraph/scenarios.py` add the risky patterns the queries are meant to find, each with
a control that they shouldn't flag.

All names, account IDs (`111122223333`, `444455556666`) and ARNs are fictional; the account
IDs are the placeholders AWS uses in its own documentation.

## How access is derived

Grants are never planted. The generator writes IAM policies the way the ontology models them
(policy → statement → effect / action / resource), and `aql/derive_effective_access.aql`
evaluates them: identity and group policies, wildcards, explicit deny, permission
boundaries, same-account scope, and AWS's access level for each action. It is a deliberately
small evaluator, not a replacement for IAM: resource policies, conditions and SCPs are not
evaluated. `src/awsgraph/policy_eval.py` applies the same rules in Python, and the
end-to-end test checks that both agree.

## Naming

Collections and attributes use the ontology's names (`IAMRole`, `canAssumeRole`,
`isPubliclyAccessible`) rather than snake_case, so a query reads like the ontology.

## Licence and credits

MIT. The vendored AWS ontology is MIT-licensed (see `ontology/vendor/`). Access levels come
from AWS's Service Authorization Reference (see `tools/build_action_catalog.py`). For other
ontologies, the
[ontology-driven graph generator](https://github.com/arango-solutions-org/ontology-driven-arango-graph-generator)
generalises the schema step.
