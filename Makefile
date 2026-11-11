# ontology -> schema -> data -> derived access -> queries
# Each step can be run on its own while reading docs/; `make all` runs the lot.

PY ?= python

.PHONY: all install forward generate validate schema load derive queries ui test e2e expected reset catalog clean

all: generate validate schema load derive queries ui

install:
	$(PY) -m pip install -e '.[dev]'

forward:            ## reach the local platform install on https://127.0.0.1:8529 (leave running; re-run if it drops)
	kubectl port-forward -n arango service/deployment-ea 8529:8529

generate:           ## ontology-driven synthetic data -> build/data.ttl
	$(PY) -m awsgraph generate

validate:           ## SHACL-validate the data against the ontology's shapes
	$(PY) -m awsgraph validate

schema:             ## collections, indexes and the three named graphs; load the ontology itself
	$(PY) -m awsgraph schema

load:               ## load build/data.ttl with ArangoRDF (PGT); link instances to classes
	$(PY) -m awsgraph load

derive:             ## evaluate policies in AQL -> hasEffectiveAccess, canList ... canTag, isAdministrator
	$(PY) -m awsgraph derive

queries:            ## run every query in aql/queries
	$(PY) -m awsgraph queries

ui:                 ## save the queries in the database for the web UI's query editor and Graph Visualizer
	$(PY) -m awsgraph ui

test:               ## unit tests (no database)
	$(PY) -m pytest

e2e:                ## end-to-end test against the database in .env
	$(PY) -m pytest -m e2e

expected:           ## re-record tests/expected from a live run and re-render docs/RESULTS.md
	UPDATE_EXPECTED=1 $(PY) -m pytest -m e2e && $(PY) tools/render_results.py

reset:              ## drop every graph and collection in the project database
	$(PY) -m awsgraph reset

catalog:            ## rebuild data/action_access_levels.csv
	$(PY) -m pip install '.[catalog]' && $(PY) tools/build_action_catalog.py

clean:
	rm -rf build .pytest_cache
