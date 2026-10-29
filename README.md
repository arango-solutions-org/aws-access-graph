# AWS access graph blueprint

A reference implementation of an AWS access graph on ArangoDB that starts from an open
ontology and works forward:

**ontology → schema → data → derived access → queries**

Each step is a small, readable module and a `make` target, so you can follow it in order:

| Step | What happens | Code | Run |
|---|---|---|---|
| 1. Ontology | Pin the open [AWS ontology](https://github.com/arango-solutions-org/aws-ontology) and pick the classes and properties this project uses | `ontology/`, `src/awsgraph/ontology.py` | |
| 2. Data | Generate a synthetic AWS estate as RDF. Every statement is checked against the ontology's domain and range, then the data is checked against its SHACL shapes | `generate.py`, `scenarios.py`, `validate.py` | `make generate validate` |
| 3. Schema | One collection per class, one edge collection per relationship, a named graph built from domain and range, and indexes. The ontology itself is loaded alongside | `schema.py` | `make schema` |
| 4. Load | Load the data with [ArangoRDF](https://github.com/ArangoDB-Community/ArangoRDF) | `load.py` | `make load` |
| 5. Derive | Evaluate IAM policies in AQL and write `canRead`, `canWrite`, `canManagePermissions` and `isAdministrator` | `aql/derive_*.aql` | `make derive` |
| 6. Query | Eight security questions in AQL, plus SPARQL and Cypher examples | `aql/queries/`, `examples/` | `make queries` |

## Quick start

```bash
git clone https://github.com/arango-solutions-org/aws-access-graph-blueprint.git
cd aws-access-graph-blueprint
python -m venv .venv && source .venv/bin/activate
make install
cp .env.example .env        # point at your ArangoDB, or:
make db                     # start ArangoDB 3.12 locally with docker compose
make all
```

`make test` runs the unit tests (no database needed). `make e2e` runs the whole pipeline
against the database in `.env` and checks every query result.

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
