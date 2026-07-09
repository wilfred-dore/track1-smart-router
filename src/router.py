"""Cascade : solveurs déterministes -> LLM local -> gate -> escalade Fireworks.

Un seul passage par tâche, jamais de boucle : chaque appel Fireworks
supplémentaire coûte des tokens, donc du classement.
"""
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
            "profit", "interest", "km", "miles")
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
        self._cache = {}

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
            print(f"[router] tâche lente ({elapsed:.1f}s) : {rec['task_id']}", file=sys.stderr)
        return rec

    def _solve_uncached(self, prompt, category, rec):
        # [1] solveurs déterministes -> 0 token
        scfg = self.cfg["solvers"]
        if scfg["enabled"] and category in scfg["use"]:
            result = solvers.solve(prompt, category)
            if result and result[1] >= scfg["min_confidence"]:
                rec["route"] = "solver"
                return result[0]

        # [2] LLM local + [3] gate de confiance -> 0 token
        ecfg = self.cfg["escalation"]
        local_answer = None
        if category not in (ecfg["always"] or []):
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

        # [4] escalade Fireworks — seulement si nécessaire
        if ecfg["enabled"] and category not in (ecfg["never"] or []):
            try:
                return self._escalate(prompt, category, rec)
            except Exception as e:
                print(f"[router] escalade échouée ({e}) : repli local", file=sys.stderr)

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
            stop=ecfg.get("stop") or None)
        rec.update(route="fireworks", model=model,
                   tokens=usage["prompt_tokens"] + usage["completion_tokens"])
        return text or "Unable to answer."
