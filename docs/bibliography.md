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
| Escalation batching (one structured call, per-task fallback on parse failure) | ✅ implemented & validated: 19/19 @ 684 tokens in 1 call via Mammouth/kimi (-36% vs per-task); flag off until a passing score is posted |

## 4. Libraries & curated lists (researched July 10)

**Category verdict up front: the entire prompt-compression ecosystem targets
1k-100k-token contexts and does not pay off below ~1-2k tokens.** Our escalated
prompts are 100-200 tokens — 10x below [leanctx](https://github.com/jia-gao/leanctx)'s
own default activation threshold (`threshold_tokens: 2000`). Compressing short
*instructions* (vs long *context*) degrades accuracy, which costs more than it saves.

### Not applicable (researched and rejected with reasons)
- [microsoft/LLMLingua / LLMLingua-2](https://github.com/microsoft/LLMLingua) — compresses the
  *context* field and deliberately leaves instruction/question untouched; our prompts are ~100%
  instruction/question.
- [liyucheng09/Selective_Context](https://github.com/liyucheng09/Selective_Context) — same
  long-context premise; dormant, no license.
- [base76-research-lab/token-compressor](https://github.com/base76-research-lab/token-compressor) —
  lossy rewrite by a local llama3.2:1b via Ollama (not in our image), validated only by cosine
  similarity ≥ 0.85 (checks similarity, not task success); 10 stars.
- [github.com/topics/token-compression](https://github.com/topics/token-compression) sweep —
  two families dominate: coding-agent context tools ([claw-compactor](https://github.com/open-compress/claw-compactor),
  squeez, tokless...) for multi-thousand-token workspaces, and vision-token pruning for VLMs.
  Nothing targets sub-300-token prompts.
- [lm-sys/RouteLLM](https://github.com/lm-sys/RouteLLM) — predicts "would GPT-4 beat Mixtral on
  this chat prompt", not "can my bundled 3B solve this task"; dormant since Aug 2024.
- [zilliztech/GPTCache](https://github.com/zilliztech/GPTCache) — semantic cache: ~0% hit rate on
  19 distinct one-shot prompts, adds wrong-answer risk. ⚠️ Its cross-run persistence variant is
  additionally **banned by the rules** ("do not hardcode or cache answers") — our cache stays
  intra-run only.
- [toon-format/toon](https://github.com/toon-format/toon) — token-efficient encoding for bulk
  tabular data; our prompts carry none.
- **Fireworks prompt caching** ([docs](https://docs.fireworks.ai/guides/prompt-caching)) —
  discounts *dollars*, not the reported `usage.prompt_tokens` we are scored on.
- Awesome-lists: [horseee/Awesome-Efficient-LLM](https://github.com/horseee/Awesome-Efficient-LLM)
  (best index — every compression entry is long-context, confirming the category verdict),
  [ZongqianLi/Prompt-Compression-Survey](https://github.com/ZongqianLi/Prompt-Compression-Survey)
  (NAACL 2025 — the de-facto awesome-prompt-compression), xlite-dev/Awesome-LLM-Inference
  (GPU serving-side, irrelevant to per-token API billing).

### Tested with real credits, held in reserve
- [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) — telegraphic
  "caveman-speak" output style (-65% output tokens claimed for coding agents).
  Convergent with our terse answer contracts. Isolated factual answers: 108 -> 79
  completion tokens (-27%), judge-approved. BUT the full-profile A/B (38 tasks,
  real API, simulated judge) measured NO gain: 1,229 vs 1,204 tokens — the batch
  already compresses answers to the floor and the telegraphic instructions cost
  their own prompt tokens. NOT shipped; a clean negative result. Bonus finding
  from the A/B: judge models disagree with each other on debatable entity labels
  (Sorbonne: location vs organization — 2/3 judges accept ours), confirming the
  freeze decision over chasing any single judge's opinion.

### Worth testing once real credits arrive
- **Fireworks grammar mode (GBNF)** ([docs](https://fireworks.ai/docs/structured-responses/structured-output-grammar-based)) —
  server-side constrained decoding: completion = exactly the answer alphabet (1-3 tokens).
  ⚠️ Caveat the research missed: our escalated categories (math, logic) *need* visible brief
  working — token-router measured 16/19 → 12/19 when it was removed — and factual needs free
  text. Grammar mode only helps if the answer-only accuracy holds; test, don't assume.
- **Tokenizer arbitrage** — the same text bills very differently per model (measured up to 38%
  between models); compare `usage` fields across kimi/minimax on identical prompts.
- **Per-category stop sequences** — kill trailing elaboration the moment the answer is complete;
  cheaper than max_tokens truncation. Config knob already exists (`escalation.stop`).

### Post-score options (local-side, zero API tokens)
- [spaCy](https://spacy.io/models/en) `en_core_web_sm` (~13 MB, MIT, NER F1≈0.845) — industrial
  NER for the local tier; map OntoNotes labels to the task's expected labels.
- [aurelio-labs/semantic-router](https://github.com/aurelio-labs/semantic-router) or an
  Avengers-Pro-style nearest-centroid ([paper](https://arxiv.org/abs/2508.12631)) — embedding
  classification if regex ever misroutes (it hasn't on our fixtures).
- llama.cpp built-in GBNF grammars on the bundled 3B — force valid local answer formats,
  fewer escalations; lighter than adding [outlines](https://github.com/dottxt-ai/outlines) or
  [guidance](https://github.com/guidance-ai/guidance) to the image.

## 5. Scientific literature (sonar sweep, July 10)

- **Batch prompting suppresses overthinking in reasoning models**: measured -74%
  reasoning tokens for o1 at batch size 15 with accuracy within ±2.4pp — the
  published explanation for our own measurement (3,510 → ~800 tokens when we
  batched kimi escalations into one call).
- **Batching interference**: ≤2pp accuracy cost for homogeneous, well-formatted
  batches (up to b=100); **5-15pp degradation when mixing heterogeneous
  reasoning problems** → we chunk reasoning-type and direct-type tasks into
  separate batch calls.
- **LLM-as-judge and bare answers**: no controlled measurement in the literature
  showing a correctness-judging penalty for answer-only responses vs
  answer+justification — our terse escalation contract is not contradicted.

## 6. Remaining levers, ranked by expected value

1. **Batch the ~7 escalations into 1-2 calls** — est. -300-400 tokens; medium risk (parsing, single point of failure).
2. **`reasoning_effort=none` + tokenizer arbitrage measurement** — one cheap live experiment once credits arrive.
3. **spaCy NER / GBNF grammars / sandboxed code execution** — only if the posted score shows a category weakness.
4. **Prompt caching** (Fireworks bills cached prompt tokens cheaper) — relevant only if batching is rejected; our system prompts repeat across ≤7 calls.
