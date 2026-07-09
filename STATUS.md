# STATUS — night of July 9-10, 2026

## Calibration sweep (July 10) → final routing policy
Three policies compared on the full eval (local 3B + mock escalation):
- A baseline + multipart-factual gate: 14/19 verified, 18/19 optimistic, 553 tk, 56 s (a wrong local
  math answer passed: n=2 self-consistency agreed on a wrong answer → flaky)
- B no self-consistency: 16/19 verified, 19/19 optimistic, 418 tk, 41 s (gambles on local math)
- C always-escalate math+logic: 13/19 verified with **0 verified failures**, 19/19 optimistic,
  912 tk, **19 s**
**Decision: C.** The accuracy gate is pass/fail and token headroom is huge (912 est. vs leader
4,268); C also cuts local CPU 3x (timing risk). `escalation.always: [math, logic]`,
self-consistency disabled. Solvers still catch trivial math at 0 tokens before escalation.
Also hardened the gate: multi-part factual questions (e.g. practice-01) now escalate instead of
letting the 3B hallucinate confidently.

## Latest results (full cascade, local Qwen2.5-3B active)
- Local LLM + mock escalation: **16/19 verified, 18/19 optimistic, 2 escalations = 340 simulated tokens**.
- Local LLM + Ollama/mistral as live stand-in Fireworks: **17/19 verified, 303 real tokens, 3 escalations**.
  Remaining failures understood: practice-01 (local 3B factual hallucination passing the gate,
  calibration knob: `gate.thresholds.factual`) and practice-02 (7B stand-in arithmetic error —
  real minimax/kimi would not make it; self-consistency correctly forced the escalation).
- Robustness: missing input / malformed JSON → exit 1; empty list / empty, huge or non-English
  prompts → exit 0 with valid schema. 4/4 PASS.
- ⚠️ Timing: ~528 CPU-seconds for 19 tasks on this M-series Mac. On 2 grading vCPUs this could
  approach the 10-minute limit → the GitHub Actions smoke test measures it on x86 with
  --cpus=2 and fails above 540 s. Mitigations if needed: lower `local.max_tokens`,
  `gate.self_consistency.enabled: false`, or `escalation.always` for slow categories.
- CI: `.github/workflows/docker.yml` builds linux/amd64 natively, smoke-tests under grading
  limits, checks compressed size, then pushes to GHCR (set the package to PUBLIC after first push).

## Done
- **Live path validated without Docker or credits**: local Ollama as a stand-in Fireworks proxy
  (`FIREWORKS_MODE=live FIREWORKS_BASE_URL=http://localhost:11434/v1 FIREWORKS_API_KEY=ollama ALLOWED_MODELS=<model> make eval`).
  Real OpenAI client, real usage, ALLOWED_MODELS resolution: everything works.
- **Reasoning-model lesson** (gemma4 via Ollama): reasoning eats the `max_tokens` budget
  and the final content comes back empty/truncated. Hardened in `src/fireworks.py`
  (`extract_text`: strips `<think>`, falls back to the reasoning field). Eval comparison
  (19 tasks, 13 escalations):
  - mistral 7B (non-reasoning), tight budgets: **16/19, 1,576 tokens** (failures = 7B arithmetic mistakes)
  - gemma4 (reasoning), budgets ×3: **17/19, 3,526 tokens**
  → on launch day, prefer a non-thinking model (kimi?) or budget generously for minimax-m3;
  calibrate with the real models as soon as credits arrive (`escalation.model_preference` + `max_tokens`).
- I/O formats extracted from the Participant Guide and implemented (`/input/tasks.json` → `/output/results.json`).
- Full pipeline in MOCK MODE: solvers → local → gate → simulated escalation with token counting.
- `config.yaml`: everything configurable (thresholds, category→model mapping, max_tokens, escalation, cache).
- 19 eval fixtures: 8 guide practice tasks (practice-04 completed with our own paragraph) + 11 variants covering all 8 categories.
- `eval/run_eval.py`: verified + optimistic accuracy, simulated tokens, per-category table.
- CPU-only linux/amd64 Dockerfile, GGUF (Qwen2.5-3B-Instruct Q4_K_M) downloaded at build time.
- Makefile: setup / eval / build / run / size. Git initialized.
- llama-cpp-python installed locally (Python 3.12 venv) + GGUF downloaded: real local-LLM path testable on this machine.

## Remaining (by priority)
1. `make eval` with the local LLM active: measure real local accuracy and per-task time
   (10-minute budget for 19 tasks on 2 vCPU — if too slow, lower `local.max_tokens` or set
   `gate.self_consistency.enabled: false`).
2. `make build && make run && make size`: validate the container end to end (⚠️ Docker unavailable
   on this machine as of July 9 evening — start Docker Desktop first; llama-cpp installed from
   precompiled CPU wheels, see the Dockerfile comment if the index is down). Alternative: GitHub Actions.
3. When Fireworks credits arrive: `.env` + `FIREWORKS_MODE=live`, evaluate on 2-3 tasks first
   (submissions are rate-limited).
4. Calibrate gate thresholds on the local eval: aim for 17/19, escalate math/logic/debug if the
   local model is weak (`escalation.always`).
5. Push the image publicly (linux/amd64) and submit. Deadline: July 11, 6pm CET.

## Watch items
- `ZERO_API_CALLS` is only a flag, but CLAUDE.md recommends keeping a few real escalations.
- The math/logic gate is shallow (presence of a number/name): local self-consistency (enabled for
  math/logic) is the real defense. Time it inside the container.
- practice-04 in the guide contains "[your own sample paragraph here]": replaced with our own
  paragraph in the fixtures.
