IMAGE ?= track1-smart-router:latest
PY := .venv/bin/python
GGUF_URL ?= https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf

.PHONY: setup setup-llm model eval input run-local build run size

setup: ## venv + dépendances coeur (suffisant pour le mode mock)
	python3 -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements.txt
	@echo "OK. Inférence locale (optionnelle) : make setup-llm && make model"

setup-llm: ## llama-cpp-python (compile ~2-5 min)
	$(PY) -m pip install -r requirements-llm.txt

model: ## télécharge le GGUF (~2 Go) dans models/
	mkdir -p models
	curl -fL --retry 3 -o models/model.gguf "$(GGUF_URL)"

eval: ## éval locale : accuracy n/19 + tokens Fireworks (mock par défaut)
	$(PY) eval/run_eval.py

input: ## génère local_io/input/tasks.json depuis les fixtures (format du guide)
	mkdir -p local_io/input local_io/output
	$(PY) -c "import json,glob; tasks=[{'task_id':t['task_id'],'prompt':t['prompt']} for p in sorted(glob.glob('eval/tasks/*.json')) for t in json.load(open(p))]; json.dump(tasks, open('local_io/input/tasks.json','w'), indent=1)"
	@echo "-> local_io/input/tasks.json"

run-local: input ## pipeline complet sans Docker (mock si pas de clé)
	INPUT_PATH=local_io/input/tasks.json OUTPUT_PATH=local_io/output/results.json $(PY) -m src.main
	@echo "-> local_io/output/results.json"

build: ## build linux/amd64 (poids bundlés au build)
	docker buildx build --platform linux/amd64 -t $(IMAGE) .

run: input ## exécute l'image comme le harness (mock forcé)
	docker run --rm --platform linux/amd64 \
		-v "$(PWD)/local_io/input:/input:ro" \
		-v "$(PWD)/local_io/output:/output" \
		-e FIREWORKS_MODE=mock \
		$(IMAGE)
	@echo "-> local_io/output/results.json"

size: ## taille de l'image + estimation compressée (limite : 10 Go)
	docker images $(IMAGE)
	@echo "Taille compressée estimée (docker save | gzip) :"
	docker save $(IMAGE) | gzip | wc -c | awk '{printf "%.2f GB\n", $$1/1e9}'
