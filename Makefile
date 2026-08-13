PYTHONPATH := src

.PHONY: test validate docs-audit check preflight-plan preflight-run preflight-verify stage1-pilot-validate stage1-pilot-smoke

test:
	PYTHONPATH=$(PYTHONPATH) python3 -m unittest discover -s tests -p "test_*.py"

validate:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/case.schema.json tests/fixtures/case_valid.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/study.schema.json experiments/000-template/manifest.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/study.schema.json experiments/001-stage1-pilot/manifest.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/run.schema.json experiments/000-template/run.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/dataset-registry.schema.json data/registry.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/case.schema.json tests/fixtures/case_valid.jsonl
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/case.schema.json data/pilot/cases.jsonl
	for path in schemas/case.schema.json schemas/study.schema.json schemas/run.schema.json schemas/dataset-registry.schema.json data/registry.json experiments/000-template/manifest.json experiments/000-template/run.json; do python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$$path" || (echo "latent-triz: $$path:0:0: invalid JSON"; exit 1); done

docs-audit:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli docs-audit --profile docs/okf-profile.toml --root . --as-of-date "$$(python3 -c 'from datetime import date; print(date.today().isoformat())')"

check: test validate docs-audit stage1-pilot-smoke

preflight-plan:
	commit-ci-preflight plan --config .commit-ci-preflight.toml

preflight-run:
	commit-ci-preflight run --config .commit-ci-preflight.toml --repository . --generation 1

preflight-verify:
	commit-ci-preflight verify --receipt .ccp/receipt.json --policy .commit-ci-policy.toml --expected-commit "$$(git rev-parse HEAD)"

stage1-pilot-validate:
	for path in schemas/pilot-packet.schema.json schemas/pilot-response.schema.json schemas/pilot-annotation.schema.json schemas/pilot-summary.schema.json; do \
	  python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$$path" || (echo "latent-triz: $$path:0:0: invalid JSON"; exit 1); \
	done
	@if [ -n "$$PILOT_PACKET" ]; then \
	  PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/pilot-packet.schema.json "$$PILOT_PACKET"; \
	fi
	@if [ -n "$$PILOT_RESPONSE" ]; then \
	  PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/pilot-response.schema.json "$$PILOT_RESPONSE"; \
	fi
	@if [ -n "$$PILOT_ANNOTATION" ]; then \
	  PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/pilot-annotation.schema.json "$$PILOT_ANNOTATION"; \
	fi
	@if [ -n "$$PILOT_SUMMARY" ]; then \
	  PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/pilot-summary.schema.json "$$PILOT_SUMMARY"; \
	fi

stage1-pilot-smoke:
	@set -eu; \
	tmpdir="$$(mktemp -d)"; \
	trap 'rm -rf "$$tmpdir"' EXIT; \
	cases=data/pilot/cases.jsonl; \
	expected_packets=data/pilot/packets.jsonl; \
	expected_summary=data/pilot/summary.json; \
	responses=data/pilot/responses.jsonl; \
	annotations=data/pilot/annotations.jsonl; \
	tmp_packets="$$tmpdir/packets.jsonl"; \
	tmp_summary="$$tmpdir/summary.json"; \
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli pilot-prepare \
	  --seed 20260812 \
	  --arms control treatment \
	  --cases "$$cases" \
	  --output "$$tmp_packets" \
	  --format jsonl; \
	if [ ! -f "$$expected_packets" ]; then \
	  echo "stage1-pilot-smoke: missing $$expected_packets"; \
	  exit 1; \
	fi; \
	cmp -s "$$tmp_packets" "$$expected_packets"; \
	echo "stage1-pilot-smoke: packets match $$expected_packets"; \
	if [ ! -f "$$responses" ]; then \
	  echo "stage1-pilot-smoke: missing $$responses"; \
	  exit 1; \
	fi; \
	if [ ! -f "$$annotations" ]; then \
	  echo "stage1-pilot-smoke: missing $$annotations"; \
	  exit 1; \
	fi; \
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli pilot-score \
	  --packets "$$expected_packets" \
	  --responses "$$responses" \
	  --annotations "$$annotations" \
	  --output "$$tmp_summary"; \
	if [ ! -f "$$expected_summary" ]; then \
	  echo "stage1-pilot-smoke: missing $$expected_summary"; \
	  exit 1; \
	fi; \
	cmp -s "$$tmp_summary" "$$expected_summary"; \
	echo "stage1-pilot-smoke: summary matches $$expected_summary"; \
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/pilot-packet.schema.json "$$expected_packets"; \
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/pilot-response.schema.json "$$responses"; \
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/pilot-annotation.schema.json "$$annotations"; \
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/pilot-summary.schema.json "$$expected_summary"
