# Track 1 — Smart Router (AMD Developer Hackathon ACT II)

Natural-language task router: answer as much as possible at **0 Fireworks
tokens**, escalate only when necessary. Goal: pass the accuracy gate (80%,
i.e. 16/19) then minimize tokens billed through `FIREWORKS_BASE_URL`.

## Architecture

```
task → [1] deterministic solvers (regex/rules)           → 0 tokens
     → [2] local GGUF 2-3B 4-bit LLM, CPU (bundled)      → 0 tokens
     → [3] confidence gate (heuristics +                 → 0 tokens
           local self-consistency)
     → [4] Fireworks escalation (model picked from       → tokens counted
           ALLOWED_MODELS, tight output contract)
```

Single pass per task, never a loop. Everything is driven by
[config.yaml](config.yaml): gate thresholds, category→model mapping,
`max_tokens`, escalation on/off, cache on/off.

## I/O formats (Participant Guide)

- Input: `/input/tasks.json` — `[ { "task_id": "...", "prompt": "..." } ]`
- Output: `/output/results.json` — `[ { "task_id": "...", "answer": "..." } ]`
- Env injected by the harness: `FIREWORKS_API_KEY`, `FIREWORKS_BASE_URL`,
  `ALLOWED_MODELS` (read at runtime, never hardcoded).

## Modes (`FIREWORKS_MODE` env var)

| Mode | Behavior |
|------|----------|
| `mock` | no network calls, simulated answers, tokens counted (estimate) |
| `live` | real calls through `FIREWORKS_BASE_URL` |
| `auto` (default) | `live` if `FIREWORKS_API_KEY` is present, else `mock` — the harness injects the key at evaluation time, so the image goes live with no change |

## Quickstart (no Fireworks key, no GPU)

```bash
make setup      # venv + core deps (use PYTHON=python3.12 if default is 3.14)
make eval       # 19 fixtures: accuracy + simulated tokens, per-category table
make run-local  # full pipeline locally (guide formats)
```

Real local inference (optional in dev, included in the Docker image):

```bash
make setup-llm  # llama-cpp-python
make model      # download the GGUF (~2 GB) into models/
make eval       # re-evaluate with the local LLM active
```

Test the live escalation path without credits, using a local Ollama server
as a stand-in Fireworks endpoint:

```bash
FIREWORKS_MODE=live FIREWORKS_BASE_URL=http://localhost:11434/v1 \
FIREWORKS_API_KEY=ollama ALLOWED_MODELS=mistral:latest make eval
```

## Docker (submission)

```bash
make build      # buildx linux/amd64, GGUF downloaded AT BUILD time and bundled
make run        # run the image the way the harness does (mock forced)
make size       # check compressed size (< 10 GB required)
```

Publishing: `docker tag track1-smart-router:latest <registry>/<image>:latest`
then `docker push` (the image must be **public**).

## Layout

```
config.yaml          all settings (nothing hardcoded in the code)
src/solvers.py       deterministic solvers (math, sentiment, NER, factual)
src/local_llm.py     llama-cpp-python wrapper (GGUF, CPU-only)
src/gate.py          zero-cost confidence gate
src/fireworks.py     OpenAI-compatible client + MockFireworksClient
src/router.py        cascade + category classification
src/main.py          I/O in the guide formats
eval/tasks/          19 fixtures (8 guide practice tasks + 11 variants)
eval/run_eval.py     accuracy n/19 + tokens, per-category table
```

## Pre-submission checklist

- [ ] `make eval` ≥ 16/19 locally with the local LLM active
- [ ] `make build && make run`: valid `results.json`, exit code 0, < 10 min
- [ ] `make size` < 10 GB
- [ ] image pushed **public** with a **linux/amd64** manifest
- [ ] no secrets and no `.env` inside the image
