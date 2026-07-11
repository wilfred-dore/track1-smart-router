"""Cascade: deterministic solvers -> local LLM -> gate -> Fireworks escalation.

A single pass per task, never a loop: every extra Fireworks call costs
tokens, hence leaderboard rank. Escalations can optionally be grouped into
one batched call (escalation.batch) with per-task fallback on parse failure.
"""
import json
import re
import sys
import time

from . import gate, solvers
from .config import by_category
from .fireworks import resolve_model

CATEGORIES = ["factual", "math", "sentiment", "summarization", "ner",
              "code_debugging", "logic", "code_generation"]

_MATH_KW = ("how many", "how much", "calculate", "compute", "percent", "%", "total",
            "sum of", "average", "speed", "per hour", "remain", "cost", "price",
            "profit", "interest", "km", "miles", "how old", "times as", "add up to")
_LOGIC_KW = ("who owns", "each own", "who won", "who is the", "logic", "puzzle",
             "deduce", "must be true", "exactly one", "neither", "either",
             "different position", "different pet", "each have", "each has")


def classify(prompt):
    p = prompt.lower()
    if "sentiment" in p:
        return "sentiment"
    if "summar" in p or "condense" in p or "tl;dr" in p:
        return "summarization"
    if "entit" in p or re.search(r"\bner\b", p):
        return "ner"
    if re.search(r"\b(bug|debug|fix)\b", p) and ("def " in prompt or "function" in p or "code" in p):
        return "code_debugging"
    if re.search(r"\b(write|implement|create)\b.*\b(function|class|script|program|code)\b", p):
        return "code_generation"
    if re.search(r"\d", p) and any(k in p for k in _MATH_KW):
        return "math"
    if any(k in p for k in _LOGIC_KW):
        return "logic"
    if re.search(r"\d", p) and re.search(r"[+\-*/=^]", p):
        return "math"
    return "factual"


class Router:
    def __init__(self, cfg, local, fw):
        self.cfg = cfg
        self.local = local
        self.fw = fw
        solvers.NER_BACKEND = cfg["solvers"].get("ner_backend", "rules")
        self._cache = {}
        budget = cfg["limits"].get("total_budget_seconds")
        self.deadline = (time.monotonic() + budget) if budget else None
        self._rushed = False
        self._defer_escalation = False

    def solve(self, task):
        t0 = time.time()
        prompt = task["prompt"]
        category = classify(prompt)
        rec = {"task_id": task.get("task_id"), "category": category,
               "route": None, "model": None, "tokens": 0, "answer": ""}

        key = re.sub(r"\s+", " ", prompt.strip().lower())
        if self.cfg["cache"]["enabled"] and key in self._cache:
            hit = dict(self._cache[key])
            hit.update(task_id=rec["task_id"], route="cache", tokens=0)
            return hit

        rec["answer"] = self._solve_uncached(prompt, category, rec)
        if self.cfg["cache"]["enabled"]:
            self._cache[key] = dict(rec)

        elapsed = time.time() - t0
        if elapsed > self.cfg["limits"]["per_task_seconds"]:
            print(f"[router] slow task ({elapsed:.1f}s): {rec['task_id']}", file=sys.stderr)
        return rec

    def solve_all(self, tasks, on_result=None):
        """Solve a task list. With escalation.batch enabled, the zero-token
        stages run per task and all pending escalations are grouped into as few
        Fireworks calls as possible; otherwise identical to per-task solve()."""
        bcfg = (self.cfg["escalation"].get("batch") or {})
        if not bcfg.get("enabled"):
            results = []
            for task in tasks:
                rec = self._safe(self.solve, task)
                results.append(rec)
                if on_result:
                    on_result(rec)
            return results

        results, pending = [], []
        for task in tasks:
            rec = self._safe(self.solve_local_only, task)
            results.append(rec)
            if rec["route"] == "pending_escalation":
                pending.append(rec)
            elif on_result:
                on_result(rec)
        # Group reasoning-type tasks separately: mixing heterogeneous reasoning
        # problems in one batch measurably degrades accuracy (5-15pp reported;
        # arXiv batch-prompting interference studies), while homogeneous batches
        # stay within ~2pp of per-task calls.
        # Solo categories bypass batching entirely: batched logic without a
        # thinking channel is non-deterministically wrong (measured), while the
        # same tasks solo are deterministic and ~6 tokens each.
        solo = set((bcfg.get("solo_categories") or []))
        for rec in [p for p in pending if p["category"] in solo]:
            pending.remove(rec)
            try:
                rec["answer"] = self._escalate(rec["prompt"], rec["category"], rec)
            except Exception as e:
                print(f"[router] solo escalation failed ({e})", file=sys.stderr)
                rec.update(route="fallback",
                           answer=rec.get("local_answer") or "Unable to answer.")
            if on_result:
                on_result(rec)
        groups = {}
        for rec in pending:
            key = ("reasoning" if rec["category"] in
                   ("math", "logic", "code_debugging", "code_generation") else "direct")
            groups.setdefault(key, []).append(rec)
        max_tasks = int(bcfg.get("max_tasks") or 10)
        for key, group in groups.items():
            for i in range(0, len(group), max_tasks):
                chunk = group[i:i + max_tasks]
                self._escalate_batch(chunk, group_kind=key)
                if on_result:
                    for rec in chunk:
                        on_result(rec)
        return results

    def _safe(self, fn, task):
        try:
            return fn(task)
        except Exception as e:
            print(f"[router] task {task.get('task_id')} failed: {e}", file=sys.stderr)
            return {"task_id": task.get("task_id"), "category": "?", "route": "error",
                    "model": None, "tokens": 0, "answer": "Unable to answer.",
                    "prompt": task.get("prompt", "")}

    def solve_local_only(self, task):
        """Zero-token stages only; marks the record 'pending_escalation' instead
        of calling Fireworks (used by the batched path)."""
        prompt = task["prompt"]
        category = classify(prompt)
        rec = {"task_id": task.get("task_id"), "category": category,
               "route": None, "model": None, "tokens": 0, "answer": "",
               "prompt": prompt}
        self._defer_escalation = True
        try:
            rec["answer"] = self._solve_uncached(prompt, category, rec)
        finally:
            self._defer_escalation = False
        return rec

    @staticmethod
    def _parse_batch_answers(text, ids):
        """Map task ids to answers from a batched response. Models don't always
        obey the JSON instruction (kimi sometimes answers as a markdown list),
        so parse both: a JSON object, else '[id] answer' segments."""
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
                return {str(k): str(v).strip() for k, v in data.items() if str(v).strip()}
            except Exception:
                pass
        markers = sorted((mm.start(), mm.end(), tid)
                         for tid in ids
                         for mm in re.finditer(re.escape(f"[{tid}]"), text))
        answers = {}
        for i, (start, end, tid) in enumerate(markers):
            stop = markers[i + 1][0] if i + 1 < len(markers) else len(text)
            seg = text[end:stop].strip()
            seg = re.sub(r"^[\s*:>\-]*(\([a-z_ ]+\))?[\s*:>\-]*", "", seg).strip()
            if seg:
                answers.setdefault(tid, seg)
        return answers

    def _escalate_batch(self, chunk, group_kind="direct"):
        """One Fireworks call for several tasks; per-task fallback on any miss.
        Reasoning-type groups may use different extra_params: killing the
        thinking channel makes logic answers non-deterministically wrong
        (measured: 3 correct runs, then 'Lee' instead of 'Sam')."""
        ecfg = self.cfg["escalation"]
        extra = (ecfg.get("extra_params_reasoning") if group_kind == "reasoning"
                 else ecfg.get("extra_params")) or None
        instructions = ecfg.get("category_instructions") or {}
        categories = sorted({r["category"] for r in chunk})
        guidance = " ".join(f"[{c}] {instructions[c]}" for c in categories if c in instructions)
        system = (ecfg["system_prompt"] + ' Independent tasks tagged [id] (category). '
                  'Return ONLY JSON: {"id": "answer", ...} with ids exactly as given. '
                  + guidance)
        user = "\n\n".join(f"[{r['task_id']}] ({r['category']}) "
                           f"{r['prompt'][:ecfg['max_prompt_chars']]}" for r in chunk)
        budget = sum(by_category(ecfg["max_tokens"], r["category"]) for r in chunk)
        try:
            model = resolve_model("default", self.cfg)
            text, usage = self.fw.chat(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                max_tokens=min(budget, 4000),
                stop=ecfg.get("stop") or None,
                extra_params=extra,
                # A grouped call legitimately takes longer than a single one;
                # the 25 s default was killing every batch on slow upstreams.
                timeout=(ecfg.get("batch") or {}).get("timeout_seconds") or 90)
            if usage.get("finish_reason") == "length":
                # Truncated batch: every parsed segment is suspect (a cut-off
                # markdown list still yields plausible-looking fragments).
                # Ship nothing from it; the per-task fallback below covers all.
                print("[router] batch truncated (finish_reason=length): "
                      "discarding batch output, per-task fallback", file=sys.stderr)
                raise RuntimeError("batch truncated")
            answers = self._parse_batch_answers(text, [r["task_id"] for r in chunk])
            per_task = (usage["prompt_tokens"] + usage["completion_tokens"]) // max(1, len(chunk))
            for rec in chunk:
                if answers.get(rec["task_id"]):
                    rec.update(route="fireworks_batch", model=model, tokens=per_task,
                               answer=answers[rec["task_id"]])
        except Exception as e:
            print(f"[router] batch escalation failed ({e}): per-task fallback", file=sys.stderr)
        for rec in chunk:  # anything the batch missed goes through the normal path
            if rec["route"] == "pending_escalation":
                try:
                    rec["answer"] = self._escalate(rec["prompt"], rec["category"], rec)
                except Exception as e:
                    print(f"[router] fallback escalation failed ({e})", file=sys.stderr)
                    rec.update(route="fallback",
                               answer=rec.get("local_answer") or "Unable to answer.")

    def _solve_uncached(self, prompt, category, rec):
        # [1] deterministic solvers -> 0 tokens
        scfg = self.cfg["solvers"]
        if scfg["enabled"] and category in scfg["use"]:
            result = solvers.solve(prompt, category)
            if result and result[1] >= scfg["min_confidence"]:
                rec["route"] = "solver"
                return result[0]

        # [2] local LLM + [3] confidence gate -> 0 tokens
        # Past the soft time budget, skip local inference (the slow stage) so the
        # container always finishes well under the 10-minute grading limit.
        ecfg = self.cfg["escalation"]
        local_answer = None
        if self.deadline and not self._rushed and time.monotonic() > self.deadline:
            self._rushed = True
            print("[router] soft time budget exceeded: switching to solver/escalation only",
                  file=sys.stderr)
        if category not in (ecfg["always"] or []) and not self._rushed:
            local_answer = self.local.generate(prompt, category)
            if local_answer:
                if not self.cfg["gate"]["enabled"]:
                    rec["route"] = "local"
                    return local_answer
                conf = gate.score(prompt, local_answer, category)
                sc = self.cfg["gate"]["self_consistency"]
                if sc["enabled"] and category in (sc.get("categories") or CATEGORIES):
                    conf += gate.self_consistency_bonus(
                        local_answer, category,
                        lambda: self.local.generate(prompt, category,
                                                    temperature=sc["temperature"]),
                        samples=sc["samples"])
                if conf >= by_category(self.cfg["gate"]["thresholds"], category):
                    rec["route"] = "local"
                    return local_answer

        # [4] Fireworks escalation — only when necessary
        if ecfg["enabled"] and category not in (ecfg["never"] or []):
            if self._defer_escalation:  # batched path: collect instead of calling
                rec["route"] = "pending_escalation"
                rec["local_answer"] = local_answer
                return local_answer or ""
            try:
                return self._escalate(prompt, category, rec)
            except Exception as e:
                print(f"[router] escalation failed ({e}): falling back to local", file=sys.stderr)

        # Escalation failed or disabled: NEVER ship an empty answer. For
        # always-escalated categories no local attempt was made yet — a 3B
        # guess scores far better than "Unable to answer." (guaranteed zero).
        if not local_answer and not self._rushed:
            local_answer = self.local.generate(prompt, category)
        rec["route"] = "local_lowconf" if local_answer else "fallback"
        return local_answer or "Unable to answer."

    def _escalate(self, prompt, category, rec):
        ecfg = self.cfg["escalation"]
        model = resolve_model(category, self.cfg)
        system = ecfg["system_prompt"]
        instruction = (ecfg.get("category_instructions") or {}).get(category)
        if instruction:
            system += " " + instruction
        text, usage = self.fw.chat(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": prompt[:ecfg["max_prompt_chars"]]}],
            max_tokens=by_category(ecfg["max_tokens"], category),
            stop=ecfg.get("stop") or None,
            extra_params=ecfg.get("extra_params") or None)
        rec.update(route="fireworks", model=model,
                   tokens=usage["prompt_tokens"] + usage["completion_tokens"])
        return text or "Unable to answer."
