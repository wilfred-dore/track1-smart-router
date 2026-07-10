# Token-Efficiency Bibliography

Working bibliography for the Track 1 smart router: every idea considered for
reducing scored Fireworks tokens, who proposed it, and the verdict for THIS
scoring model. Kept honest: rejected ideas stay listed with the reason.

**Scoring reality check** — only tokens routed through `FIREWORKS_BASE_URL`
count; the 80% accuracy gate is pass/fail before tokens matter at all; our
escalated prompts are short (~100-200 tokens). Any technique must be judged
against those three facts, not against generic LLM-cost folklore.

---

## 1. Wilfred's ideas

| Idea | Verdict | Why |
|---|---|---|
| Use local LLMs on the Mac (Ollama) as test infrastructure | ✅ Adopted | Ollama served as a stand-in Fireworks endpoint: validated the live client path with zero credits |
| Use the Mammouth AI aggregator as a stand-in proxy | ✅ Adopted, decisive | Only way to calibrate on the real model families (kimi 19/19 @ 1,059 tk vs minimax 18/19 @ 1,622) before credits arrived |
| Pre-prompt routing orientation | ✅ Adopted | Per-category system-prompt instructions; independently validated by yassai's A/B (-12% tokens) |
| Formal verification to reduce hallucinations (Formel AI / Kortex-style) | 🟡 Adopted in spirit | Full reasoning layers are overkill; the cheap version is our deterministic gate: `ast.parse` on code, sentence-count checks, label checks |
| Design-by-contract (Gherkin / Eiffel) | 🟡 Adopted in spirit | Per-category output contracts (tight `max_tokens`, format instructions) are exactly postconditions |
| Fine-tune on observed eval questions | ❌ Rejected | Eval set is hidden, uses unseen variants, and hardcoding is banned; also slow and costly |
| Optuna hyperparameter search | ❌ Rejected | 19 local fixtures cannot support fine-grained search without overfitting; we compare *policies*, not decimals |
| Translate exchanges to Chinese before sending | ❌ Rejected | We only control ~40 input tokens (system prompt); task prompts must go verbatim (a 3B translation corrupts numbers/names, and the judge scores against the original intent); answers must be in English per the rules |
| Binary / base64 exchanges | ❌ Rejected | BPE tokenizers shatter high-entropy strings: costs MORE tokens, not fewer |
| recursiveMAS / multi-agent exchanges | ❌ Rejected | Every extra exchange is billed; anti-pattern under this scoring |
| spaCy industrial NLP for NER | 🕐 Post-score option | `en_core_web_sm` (~12 MB, CPU) would generalize better than our gazetteers on unseen variants; +1 dependency at h-30 not worth it while NER is not a measured weakness |

## 2. Competitors' ideas (public repos, studied and credited — no code copied)

### Adopted into our pipeline
| Idea | Source | Status |
|---|---|---|
| Defensive parsing of harness-injected `ALLOWED_MODELS` (JSON arrays, quotes, separators) | [DavidOrtsac/frugal-router](https://github.com/DavidOrtsac/frugal-router) (lost 7 submissions to this) | ✅ shipped |
| Thread count from cgroup v2 `cpu.max` — `os.cpu_count()` lies under Docker quotas | [Anbu-00001/Minimalist](https://github.com/Anbu-00001/Minimalist) | ✅ shipped |
| Internal soft deadline under the 10-min limit | [ashaibani/yassai](https://github.com/ashaibani/yassai) (9m30) | ✅ shipped (480 s) |
| Deterministic zero-token validators as escalation gates (`ast.parse`) | [VisistaJayanti/AMD_Hackathon_Track1](https://github.com/VisistaJayanti/AMD_Hackathon_Track1) | ✅ shipped |
| Non-English drift detector on small-model output | [my5757980/amd-hackathon-track1](https://github.com/my5757980/amd-hackathon-track1) | ✅ shipped |
| Answer with the question's exact labels (judge penalizes wording drift) | Minimalist's V22 post-mortem (~8 logic tasks lost on labels alone) | ✅ shipped (prompt instruction) |
| `reasoning_effort=none` control | [omerdduran/token-router](https://github.com/omerdduran/token-router): minimax-m3 16/19 with it, **gemma-4 returns empty** under it | ✅ knob shipped (`extra_params`), enable only after live test |
| Atomic incremental `results.json` (valid at any kill point; timeout ≠ zero) | [Kunsh162007/Hybrid-token-efficient-routing-agent](https://github.com/Kunsh162007/Hybrid-token-efficient-routing-agent) | ✅ shipped |
| Route by *verifiability*, not difficulty — escalate what cannot be checked for free | Meta-lesson across all serious repos; [QasimKhan5d/amd-hack-track1-router](https://github.com/QasimKhan5d/amd-hack-track1-router) measured local factual at 3/9 on real-benchmark variants | ✅ shipped (`always: [math, logic, factual]`) |

### Noted, deliberately not (yet) adopted
| Idea | Source | Verdict |
|---|---|---|
| **Batch escalations into 1-2 calls** (-79% tokens measured at batch-40; variance blows up past ~20) | yassai | 🕐 Next token lever (~1,050 → ~700 est.) — single point of failure, only after a posted passing score |
| Render long passages as images (Fireworks bills vision by geometry, not BPE; -52-69% beyond ~2,000 chars) | yassai (`text2img`) | ❌ Our escalated prompts are short; even yassai's auto mode stays text-only on the real 19 tasks |
| 1-token remote YES/NO judge of local answers (middle rung between free and full generation) | Kunsh162007 | 🕐 Post-score option; adds calls and complexity |
| Tokenizer arbitrage: pin the model whose tokenizer bills the same text cheapest | token-router (`PREFERRED_MODEL`) | 🕐 Worth one measurement once real credits arrive |
| Record-and-replay threshold tuning (dump local+remote answers once, sweep thresholds offline for free) | frugal-router (`eval/frontier.py`) | 🟡 Our config-sweep achieved the same at smaller scale |
| Qualification-first ladder — **the leaderboard keeps the LAST score, not the best** | frugal-router | ✅ Adopted as an operational rule: freeze after a good score |
| Calibrate on real benchmark samples (TriviaQA/GSM8K/CoNLL/BBH), not self-authored fixtures | QasimKhan5d's `ACCURACY_GATE_FAILED` post-mortem | 🟡 Partially: 8 official practice tasks + 11 variants; their lesson drove our factual escalation instead |
| Self-consistency "loose" on factual (content-word overlap across 3 samples: independent hallucinations don't agree) | QasimKhan5d | ❌ Superseded — we escalate factual outright, cheaper than 3 local samples on 2 vCPU |
| Sandboxed *execution* of generated code, without auto-generated tests (biased) | QasimKhan5d (citing ACL 2025) | 🕐 Post-score option; `ast.parse` is the cheap 80% |
| CSP solver for logic puzzles, uniqueness as the guardrail; solver can override the model | Minimalist | ❌ We escalate logic; a frontier model beats a hand-rolled CSP translator built in one night |
| Grammar-constrained decoding (GBNF) for labels/JSON on the local model | Minimalist | 🕐 Post-score option (llama-cpp supports it) |
| Small-model self-reported confidence as a gate | reckylurker, codelegger | ❌ Measured useless by QasimKhan5d (always 8-10/10); our gate is deterministic checks instead |
| TF-IDF / MiniLM-centroid classifiers instead of regex | QasimKhan5d, sathya-026 | 🟡 Our regex classifier has not misrouted any fixture; revisit only on evidence |
| minimax-m3 returns 36% empty answers on constraint puzzles (invisible CoT burns the budget) vs 0% for kimi | [sathya-026/Hybrid-Token-Efficient-Routing-Agent](https://github.com/sathya-026/Hybrid-Token-Efficient-Routing-Agent) | ✅ Independently confirms our kimi-first calibration |

## 3. AI's (Claude's) ideas

| Idea | Status |
|---|---|
| Local-first cascade with deterministic solvers ahead of everything (≈6/19 tasks at 0 tokens, 0 model load) | ✅ core design |
| Zero-cost heuristic confidence gate with per-category checks + multipart-factual penalty | ✅ shipped |
| `FIREWORKS_MODE` auto (mock without key, live when the harness injects one) — build and test with zero credits | ✅ shipped |
| Stand-in-proxy testing methodology (Ollama, then Mammouth for the real model families) | ✅ decisive for model choice |
| Reasoning-model output recovery (`<think>` stripping + reasoning-field fallback) | ✅ shipped, caught a real empty-answer bug |
| CI smoke test at the exact grading limits (amd64, 4 GB, 2 vCPU, timing + schema + size gates before any push) | ✅ caught the musl-wheel bug before a submission slot was burned |
| Policy sweep instead of hyperparameter search (3 qualitative configs × full eval) | ✅ chose the routing policy |
| Escalation batching design (map task_ids in one structured call, per-task fallback on parse failure) | 🕐 designed, unimplemented — next lever |

## 4. Libraries & curated lists

*Pending: a research sweep of prompt-compression libraries (LLMLingua et al.),
routing frameworks (RouteLLM), semantic caches (GPTCache), GitHub's
`token-compression` topic, and awesome-lists — with per-tool verdicts for this
scoring model. Will be merged here when the review completes.*

## 5. Remaining levers, ranked by expected value

1. **Batch the ~7 escalations into 1-2 calls** — est. -300-400 tokens; medium risk (parsing, single point of failure).
2. **`reasoning_effort=none` + tokenizer arbitrage measurement** — one cheap live experiment once credits arrive.
3. **spaCy NER / GBNF grammars / sandboxed code execution** — only if the posted score shows a category weakness.
4. **Prompt caching** (Fireworks bills cached prompt tokens cheaper) — relevant only if batching is rejected; our system prompts repeat across ≤7 calls.
