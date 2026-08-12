PYTHONPATH := src

.PHONY: test validate docs-audit check

test:
	PYTHONPATH=$(PYTHONPATH) python3 -m unittest discover -s tests -p "test_*.py"

validate:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/case.schema.json tests/fixtures/case_valid.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/study.schema.json experiments/000-template/manifest.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/run.schema.json experiments/000-template/run.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/dataset-registry.schema.json data/registry.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/case.schema.json tests/fixtures/case_valid.jsonl
	for path in schemas/case.schema.json schemas/study.schema.json schemas/run.schema.json schemas/dataset-registry.schema.json data/registry.json experiments/000-template/manifest.json experiments/000-template/run.json; do python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$$path" || (echo "latent-triz: $$path:0:0: invalid JSON"; exit 1); done

docs-audit:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli docs-audit --profile docs/okf-profile.toml --root . --as-of-date "$$(python3 -c 'from datetime import date; print(date.today().isoformat())')"

check: test validate docs-audit
