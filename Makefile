IMAGE ?= track1-smart-router:latest
PYTHON ?= python3   # e.g. make setup PYTHON=python3.12 (llama-cpp-python does not build on 3.14 yet)
PY := .venv/bin/python
GGUF_URL ?= https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf

.PHONY: setup setup-llm model eval input run-local build run size

setup: ## venv + core dependencies (enough for mock mode)
	$(PYTHON) -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements.txt
	@echo "OK. Local inference (optional): make setup-llm && make model"

setup-llm: ## llama-cpp-python (compiles ~2-5 min)
	$(PY) -m pip install -r requirements-llm.txt

model: ## download the GGUF (~2 GB) into models/
	mkdir -p models
	curl -fL --retry 3 -o models/model.gguf "$(GGUF_URL)"

eval: ## local eval: accuracy n/19 + Fireworks tokens (mock by default)
	$(PY) eval/run_eval.py

input: ## generate local_io/input/tasks.json from the fixtures (guide format)
	mkdir -p local_io/input local_io/output
	$(PY) -c "import json,glob; tasks=[{'task_id':t['task_id'],'prompt':t['prompt']} for p in sorted(glob.glob('eval/tasks/*.json')) for t in json.load(open(p))]; json.dump(tasks, open('local_io/input/tasks.json','w'), indent=1)"
	@echo "-> local_io/input/tasks.json"

run-local: input ## full pipeline without Docker (mock if no key)
	INPUT_PATH=local_io/input/tasks.json OUTPUT_PATH=local_io/output/results.json $(PY) -m src.main
	@echo "-> local_io/output/results.json"

build: ## linux/amd64 build (weights bundled at build time)
	docker buildx build --platform linux/amd64 -t $(IMAGE) .

run: input ## run the image the way the harness does (mock forced)
	docker run --rm --platform linux/amd64 \
		-v "$(PWD)/local_io/input:/input:ro" \
		-v "$(PWD)/local_io/output:/output" \
		-e FIREWORKS_MODE=mock \
		$(IMAGE)
	@echo "-> local_io/output/results.json"

size: ## image size + compressed estimate (limit: 10 GB)
	docker images $(IMAGE)
	@echo "Estimated compressed size (docker save | gzip):"
	docker save $(IMAGE) | gzip | wc -c | awk '{printf "%.2f GB\n", $$1/1e9}'
