PYTHONPATH := src

.PHONY: test validate docs-audit check preflight-plan preflight-run preflight-verify model-preflight dataset-audit readiness lab01 lab01-render lab02 lab02-render lab03 lab03-render lab04 lab04-render pilot-export-evaluator stage1-pilot-validate stage1-pilot-smoke lab lab-render

test:
	PYTHONPATH=$(PYTHONPATH) python3 -m unittest discover -s tests -p "test_*.py"

validate:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/case.schema.json tests/fixtures/case_valid.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/study.schema.json experiments/000-template/manifest.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/study.schema.json experiments/001-stage1-pilot/manifest.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/run.schema.json experiments/000-template/run.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/dataset-registry.schema.json data/registry.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/claim.schema.json data/claims.jsonl
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/lab01-manifest.schema.json experiments/lab01-model-anatomy/manifest.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/dataset-annotation.schema.json data/pilot/dataset-annotations.jsonl
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/lab03-config.schema.json experiments/lab03-behavioral-baselines/config.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/lab03-result.schema.json results/lab03/behavioral-baselines/summary.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli claims-audit --registry data/claims.jsonl --root .
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/case.schema.json tests/fixtures/case_valid.jsonl
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/case.schema.json data/pilot/cases.jsonl
	for path in schemas/case.schema.json schemas/study.schema.json schemas/run.schema.json schemas/dataset-registry.schema.json schemas/claim.schema.json data/registry.json experiments/000-template/manifest.json experiments/000-template/run.json; do python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$$path" || (echo "latent-triz: $$path:0:0: invalid JSON"; exit 1); done

docs-audit:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli docs-audit --profile docs/okf-profile.toml --root . --as-of-date "$$(python3 -c 'from datetime import date; print(date.today().isoformat())')"

check:
	PYTHONPATH=$(PYTHONPATH) python3 scripts/repository_check.py

preflight-plan:
	commit-ci-preflight plan --config .commit-ci-preflight.toml

preflight-run:
	commit-ci-preflight run --config .commit-ci-preflight.toml --repository . --generation 1

preflight-verify:
	commit-ci-preflight verify --receipt .ccp/receipt.json --policy .commit-ci-policy.toml --expected-commit "$$(git rev-parse HEAD)"

model-preflight:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli model-preflight --manifest experiments/001-stage1-pilot/model-candidates.jsonl

dataset-audit:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli dataset-audit --plan experiments/001-stage1-pilot/dataset-plan.json --cases data/pilot/cases.jsonl --mode development

readiness:
	@if [ "$(TARGET)" = "foundation" ]; then \
	  $(MAKE) check; \
	elif [ "$(TARGET)" = "lab01" ]; then \
	  test -n "$(LAB01_MODEL_ROOT)" || (echo "LAB01_MODEL_ROOT is required"; exit 2); \
	  $(MAKE) lab01-render LAB01_MODEL_ROOT="$(LAB01_MODEL_ROOT)"; \
	elif [ "$(TARGET)" = "lab02" ]; then \
	  $(MAKE) lab02-render; \
	elif [ "$(TARGET)" = "lab03" ]; then \
	  $(MAKE) lab03-render; \
	elif [ "$(TARGET)" = "lab04" ]; then \
	  $(MAKE) lab04-render; \
	elif [ "$(TARGET)" = "exp001" ]; then \
	  $(MAKE) model-preflight; \
	  $(MAKE) dataset-audit; \
	else \
	  echo "TARGET must be foundation, lab01, lab02, lab03, lab04, or exp001"; exit 2; \
	fi

lab01-render:
	@test -n "$(LAB01_MODEL_ROOT)" || (echo "LAB01_MODEL_ROOT is required"; exit 2)
	PYTHONPATH=$(PYTHONPATH) .venv/bin/python -m latent_triz.lab01_runner \
	  --model-root "$(LAB01_MODEL_ROOT)" \
	  --prompts experiments/lab01-model-anatomy/prompts.jsonl \
	  --output-dir results/lab01/model-anatomy

lab01: lab01-render
	@echo "Lab 01 report: results/lab01/model-anatomy/report.html"

lab02-render:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.lab02_runner \
	  --plan experiments/001-stage1-pilot/dataset-plan.json \
	  --cases data/pilot/cases.jsonl \
	  --annotations data/pilot/dataset-annotations.jsonl \
	  --registry-entry experiments/001-stage1-pilot/dataset-registry-entry.json \
	  --registry-manifest data/registry.json \
	  --output-dir results/lab02/dataset-anatomy

lab02: lab02-render
	@echo "Lab 02 report: results/lab02/dataset-anatomy/report.html"

lab03-render:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.lab03_runner \
	  --cases data/pilot/cases.jsonl \
	  --snapshot results/lab02/dataset-anatomy/snapshot_manifest.json \
	  --config experiments/lab03-behavioral-baselines/config.json \
	  --output-dir results/lab03/behavioral-baselines

lab03: lab03-render
	@echo "Lab 03 report: results/lab03/behavioral-baselines/report.html"

lab04-render:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.lab04_runner \
	  --cases data/pilot/cases.jsonl \
	  --representations data/pilot/representations.jsonl \
	  --config experiments/lab04-decodability/config.json \
	  --predecessor-lab01-summary results/lab01/model-anatomy/parity_report.json \
	  --predecessor-lab02-summary results/lab02/dataset-anatomy/summary.json \
	  --predecessor-lab03-summary results/lab03/behavioral-baselines/summary.json \
	  --output-dir results/lab04/decodability

lab04: lab04-render
	@echo "Lab 04 report: results/lab04/decodability/report.html"

pilot-export-evaluator:
	@test -n "$(EVALUATOR_OUTPUT)" || (echo "EVALUATOR_OUTPUT is required"; exit 2)
	@test -n "$(ALLOCATION_KEY_OUTPUT)" || (echo "ALLOCATION_KEY_OUTPUT is required"; exit 2)
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli pilot-export-evaluator \
	  --packets data/pilot/packets.jsonl \
	  --responses data/pilot/responses.jsonl \
	  --evaluator-output "$(EVALUATOR_OUTPUT)" \
	  --key-output "$(ALLOCATION_KEY_OUTPUT)"

stage1-pilot-validate:
	for path in schemas/pilot-packet.schema.json schemas/pilot-response.schema.json schemas/pilot-annotation.schema.json schemas/pilot-summary.schema.json schemas/evaluator-packet.schema.json schemas/allocation-key.schema.json; do \
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

lab:
	$(MAKE) stage1-pilot-smoke
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli lab00 --output artifacts/lab00/index.html --open

lab-render:
	$(MAKE) stage1-pilot-smoke
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli lab00 --output artifacts/lab00/index.html
