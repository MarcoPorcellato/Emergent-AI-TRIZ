PYTHONPATH := src

.PHONY: test validate docs-audit check schema-cross-validate preflight-plan preflight-run preflight-verify model-preflight dataset-audit dataset-wave1-audit wave1-surface-audit wave1-surface-audit-render wave1-annotation-audit readiness lab00 lab00-render lab01-setup lab01-acquire lab01-bootstrap lab01 lab01-render lab01-representations lab02 lab02-render lab03 lab03-render lab04 lab04-render lab05 lab05-render annotate annotate-serve annotate-wave1 pilot-export-evaluator stage1-pilot-validate stage1-pilot-smoke lab lab-render a0-corpus

LAB01_MODEL_ROOT ?= artifacts/models/pythia-70m-deduped-e93a9faa
LAB01_PYTHON ?= .venv/bin/python
LAB01_ADMISSION_TIMEOUT ?= 30

LAB_SUITE_OUTPUT ?= artifacts/lab/index.html
ANNOTATION_RATER_ID ?= local_rater
ANNOTATION_OUTPUT ?= artifacts/annotations/dataset-annotations.jsonl
ANNOTATION_PORT ?= 8765

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
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/annotation-guide.schema.json experiments/001-stage1-pilot/annotation-guide.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/candidate-batch.schema.json data/candidates/wave1-manifest.json
	python3 -c 'import json; json.load(open("schemas/blinded-annotation-audit.schema.json"))'
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/case.schema.json data/candidates/wave1-model-generated.jsonl
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/lab03-config.schema.json experiments/lab03-behavioral-baselines/config.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/lab03-config.schema.json experiments/wave1-surface-audit/config.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/lab03-result.schema.json results/lab03/behavioral-baselines/summary.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/representation-extractor-config.schema.json experiments/lab01-model-representations/config.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/lab03-result.schema.json results/wave1/surface-audit/summary.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/lab05-config.schema.json experiments/lab05-candidate-directions/config.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/lab05-result.schema.json results/lab05/candidate-directions/summary.json
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli claims-audit --registry data/claims.jsonl --root .
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/case.schema.json tests/fixtures/case_valid.jsonl
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli validate --schema schemas/case.schema.json data/pilot/cases.jsonl
	for path in schemas/case.schema.json schemas/study.schema.json schemas/run.schema.json schemas/dataset-registry.schema.json schemas/claim.schema.json data/registry.json experiments/000-template/manifest.json experiments/000-template/run.json; do python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$$path" || (echo "latent-triz: $$path:0:0: invalid JSON"; exit 1); done

docs-audit:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli docs-audit --profile docs/okf-profile.toml --root . --as-of-date "$$(python3 -c 'from datetime import date; print(date.today().isoformat())')"

check:
	PYTHONPATH=$(PYTHONPATH) python3 scripts/repository_check.py

schema-cross-validate:
	PYTHONPATH=$(PYTHONPATH) python3 scripts/schema_cross_validate.py

a0-corpus:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli a0-corpus \
	  --protocol experiments/a0-automated-weak-proxy/protocol.json \
	  --output-dir data/a0
	@echo "A0 foundation generated. Activation and statistical stages are not yet executed."

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

dataset-wave1-audit:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli candidate-audit \
	  --manifest data/candidates/wave1-manifest.json \
	  --cases data/candidates/wave1-model-generated.jsonl

wave1-surface-audit-render:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.lab03_runner \
	  --cases data/candidates/wave1-model-generated.jsonl \
	  --snapshot results/lab02/dataset-anatomy/snapshot_manifest.json \
	  --config experiments/wave1-surface-audit/config.json \
	  --output-dir results/wave1/surface-audit

wave1-surface-audit: wave1-surface-audit-render
	@echo "Wave 1 surface audit: results/wave1/surface-audit/report.html"

wave1-annotation-audit:
	@test -n "$(ANNOTATION_FILES)" || (echo "ANNOTATION_FILES requires one JSONL path per independent rater"; exit 2)
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli annotation-audit \
	  --cases data/candidates/wave1-model-generated.jsonl \
	  --guide experiments/001-stage1-pilot/annotation-guide.json \
	  --schema schemas/dataset-annotation.schema.json \
	  --annotations $(ANNOTATION_FILES) \
	  --minimum-distinct-raters 2 --agreement-threshold 0.8 \
	  --maximum-abstention-rate 0.2 \
	  --output artifacts/annotations/wave1-audit.json

readiness:
	@if [ "$(TARGET)" = "foundation" ]; then \
	  $(MAKE) check; \
	elif [ "$(TARGET)" = "lab01" ]; then \
	  $(MAKE) lab01-render LAB01_MODEL_ROOT="$(LAB01_MODEL_ROOT)"; \
	elif [ "$(TARGET)" = "lab02" ]; then \
	  $(MAKE) lab02-render; \
	elif [ "$(TARGET)" = "lab03" ]; then \
	  $(MAKE) lab03-render; \
	elif [ "$(TARGET)" = "lab04" ]; then \
	  $(MAKE) lab04-render; \
	elif [ "$(TARGET)" = "lab05" ]; then \
	  $(MAKE) lab05-render; \
	elif [ "$(TARGET)" = "exp001" ]; then \
	  $(MAKE) model-preflight; \
	  $(MAKE) dataset-audit; \
	else \
	  echo "TARGET must be foundation, lab01, lab02, lab03, lab04, lab05, or exp001"; exit 2; \
	fi

lab01-setup:
	@test -x "$(LAB01_PYTHON)" || python3.11 -m venv .venv
	@"$(LAB01_PYTHON)" -c "import torch, transformers, safetensors, huggingface_hub" 2>/dev/null || "$(LAB01_PYTHON)" -m pip install -r requirements-lab01.lock

lab01-acquire: lab01-setup
	PYTHONPATH=$(PYTHONPATH) "$(LAB01_PYTHON)" -m latent_triz.lab01_acquire \
	  --model-root "$(LAB01_MODEL_ROOT)" \
	  --allow-download

lab01-render:
	@test -x "$(LAB01_PYTHON)" || (echo "Run make lab01-setup first"; exit 2)
	PYTHONPATH=$(PYTHONPATH) commit-ci-preflight guard exec \
	  --admission-timeout-seconds "$(LAB01_ADMISSION_TIMEOUT)" \
	  --timeout-seconds 900 -- \
	  "$(LAB01_PYTHON)" -m latent_triz.lab01_runner \
	  --model-root "$(LAB01_MODEL_ROOT)" \
	  --prompts experiments/lab01-model-anatomy/prompts.jsonl \
	  --output-dir results/lab01/model-anatomy

lab01: lab01-render
	@echo "Lab 01 report: results/lab01/model-anatomy/report.html"

lab01-representations:
	@test -x "$(LAB01_PYTHON)" || (echo "Run make lab01-setup first"; exit 2)
	PYTHONPATH=$(PYTHONPATH) commit-ci-preflight guard exec \
	  --admission-timeout-seconds "$(LAB01_ADMISSION_TIMEOUT)" \
	  --timeout-seconds 900 -- \
	  "$(LAB01_PYTHON)" -m latent_triz.representation_extractor \
	  --config experiments/lab01-model-representations/config.json
	@echo "Lab 01 representation extraction: results/lab01/model-representations"

lab01-bootstrap: lab01-acquire
	@$(MAKE) lab01 LAB01_MODEL_ROOT="$(LAB01_MODEL_ROOT)" LAB01_PYTHON="$(LAB01_PYTHON)"

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

lab05-render:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.lab05_runner \
	  --cases data/pilot/cases.jsonl \
	  --representations data/pilot/representations.jsonl \
	  --config experiments/lab05-candidate-directions/config.json \
	  --predecessor-lab04-summary results/lab04/decodability/summary.json \
	  --output-dir results/lab05/candidate-directions

lab05: lab05-render
	@echo "Lab 05 report: results/lab05/candidate-directions/report.html"

annotate:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli annotation-workbench \
	  --cases data/pilot/cases.jsonl \
	  --guide experiments/001-stage1-pilot/annotation-guide.json \
	  --schema schemas/dataset-annotation.schema.json \
	  --output "$(ANNOTATION_OUTPUT)" --rater-id "$(ANNOTATION_RATER_ID)" \
	  --port "$(ANNOTATION_PORT)" --open

annotate-serve:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli annotation-workbench \
	  --cases data/pilot/cases.jsonl \
	  --guide experiments/001-stage1-pilot/annotation-guide.json \
	  --schema schemas/dataset-annotation.schema.json \
	  --output "$(ANNOTATION_OUTPUT)" --rater-id "$(ANNOTATION_RATER_ID)" \
	  --port "$(ANNOTATION_PORT)"

annotate-wave1:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli annotation-workbench \
	  --cases data/candidates/wave1-model-generated.jsonl \
	  --guide experiments/001-stage1-pilot/annotation-guide.json \
	  --schema schemas/dataset-annotation.schema.json \
	  --output "artifacts/annotations/wave1-$(ANNOTATION_RATER_ID).jsonl" \
	  --rater-id "$(ANNOTATION_RATER_ID)" --port "$(ANNOTATION_PORT)" --open

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

lab00:
	$(MAKE) stage1-pilot-smoke
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli lab00 --output artifacts/lab00/index.html --open

lab00-render:
	$(MAKE) stage1-pilot-smoke
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli lab00 --output artifacts/lab00/index.html

lab:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli lab-suite --root . --output $(LAB_SUITE_OUTPUT) --open

lab-render:
	PYTHONPATH=$(PYTHONPATH) python3 -m latent_triz.cli lab-suite --root . --output $(LAB_SUITE_OUTPUT)
