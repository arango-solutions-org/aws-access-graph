# ontology -> schema -> data -> derived access -> queries
# Each step can be run on its own while reading docs/; `make all` runs the lot.

PY ?= python

.PHONY: all install db generate validate schema load derive queries test e2e reset catalog clean

all: generate validate schema load derive queries

install:
	$(PY) -m pip install -e '.[dev]'

db:                 ## start a local ArangoDB 3.12 (docker compose)
	docker compose up -d --wait

generate:           ## ontology-driven synthetic data -> build/data.ttl
	$(PY) -m awsgraph generate

validate:           ## SHACL-validate the data against the ontology's shapes
	$(PY) -m awsgraph validate

schema:             ## collections, indexes and named graph from the ontology; load the ontology itself
	$(PY) -m awsgraph schema

load:               ## load build/data.ttl with ArangoRDF (PGT)
	$(PY) -m awsgraph load

derive:             ## evaluate policies in AQL -> canRead / canWrite / canManagePermissions, isAdministrator
	$(PY) -m awsgraph derive

queries:            ## run every query in aql/queries
	$(PY) -m awsgraph queries

test:               ## unit tests (no database)
	$(PY) -m pytest

e2e:                ## end-to-end test against the database in .env
	$(PY) -m pytest -m e2e

reset:              ## drop the graph and every collection in the project database
	$(PY) -m awsgraph reset

catalog:            ## rebuild data/action_access_levels.csv
	$(PY) -m pip install '.[catalog]' && $(PY) tools/build_action_catalog.py

clean:
	rm -rf build .pytest_cache
