#!/usr/bin/env python3
"""Évalue le pipeline sur les 19 fixtures locales (mode mock par défaut).

Deux lectures de l'accuracy :
  - vérifiée  : la réponse passe le checker local (regex/nombre/contenu)
  - optimiste : les tâches escaladées en mode mock sont supposées correctes
                (un modèle Fireworks de la liste les réussirait) — comptées à part.
Lancer en live : FIREWORKS_MODE=live python3 eval/run_eval.py (nécessite .env).
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FIREWORKS_MODE", "mock")

from src.config import load_config, load_dotenv  # noqa: E402
from src.fireworks import get_client  # noqa: E402
from src.local_llm import LocalLLM  # noqa: E402
from src.router import Router  # noqa: E402

GATE_THRESHOLD = 0.80  # gate d'accuracy du leaderboard


def _numbers(text):
    return [float(n.replace(",", "")) for n in re.findall(r"-?\d[\d,]*\.?\d*", text)]


def _sentences(text):
    return [s for s in re.split(r"[.!?]+(?:\s|$)", text.strip()) if s.strip()]


def check(answer, spec):
    if "all" in spec:
        return all(check(answer, s) for s in spec["all"])
    if "any" in spec:
        return any(check(answer, s) for s in spec["any"])
    kind = spec["type"]
    low = answer.lower()
    if kind == "contains_any":
        return any(v.lower() in low for v in spec["values"])
    if kind == "contains_all":
        return all(v.lower() in low for v in spec["values"])
    if kind == "number":
        return any(abs(n - spec["value"]) < 1e-6 for n in _numbers(answer))
    if kind == "regex":
        flags = re.S if spec.get("case_sensitive") else re.I | re.S
        return re.search(spec["value"], answer, flags) is not None
    if kind == "max_sentences":
        return len(_sentences(answer)) <= spec["value"]
    raise ValueError(f"check inconnu : {spec}")


def main():
    load_dotenv()
    root = os.path.dirname(os.path.abspath(__file__))
    fixtures = []
    for path in sorted(glob.glob(os.path.join(root, "tasks", "*.json"))):
        with open(path, encoding="utf-8") as f:
            fixtures.extend(json.load(f))

    cfg = load_config()
    router = Router(cfg, LocalLLM(cfg), get_client(cfg))

    rows = []
    for fx in fixtures:
        rec = router.solve({"task_id": fx["task_id"], "prompt": fx["prompt"]})
        assumed = rec["route"] == "fireworks" and router.fw.is_mock
        rows.append({**rec, "expected_cat": fx["category"],
                     "ok": None if assumed else check(rec["answer"], fx["check"])})

    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["expected_cat"]].append(r)

    print(f"\n{'catégorie':<16} {'n':>2} {'solver':>6} {'local':>5} {'fw':>3} "
          f"{'ok':>3} {'ok?':>3} {'ko':>3} {'tokens':>7}")
    print("-" * 56)
    for cat in sorted(by_cat):
        rs = by_cat[cat]
        routes = defaultdict(int)
        for r in rs:
            routes[r["route"]] += 1
        print(f"{cat:<16} {len(rs):>2} {routes['solver']:>6} {routes['local']:>5} "
              f"{routes['fireworks']:>3} "
              f"{sum(1 for r in rs if r['ok'] is True):>3} "
              f"{sum(1 for r in rs if r['ok'] is None):>3} "
              f"{sum(1 for r in rs if r['ok'] is False):>3} "
              f"{sum(r['tokens'] for r in rs):>7}")

    misrouted = [r for r in rows if r["category"] != r["expected_cat"]]
    if misrouted:
        print("\nMal classées par le routeur :")
        for r in misrouted:
            print(f"  {r['task_id']}: attendu={r['expected_cat']} obtenu={r['category']}")

    failed = [r for r in rows if r["ok"] is False]
    if failed:
        print("\nÉchecs vérifiés :")
        for r in failed:
            print(f"  {r['task_id']} [{r['route']}]: {r['answer'][:120]!r}")

    verified = sum(1 for r in rows if r["ok"] is True)
    assumed = sum(1 for r in rows if r["ok"] is None)
    total = len(rows)
    usage = router.fw.usage_summary()
    mock = " simulés (MOCK)" if router.fw.is_mock else ""

    print(f"\nAccuracy vérifiée localement : {verified}/{total}")
    print(f"Accuracy optimiste (escalades supposées justes) : {verified + assumed}/{total} "
          f"— gate leaderboard : {GATE_THRESHOLD:.0%} soit {int(total * GATE_THRESHOLD) + 1}/{total}")
    print(f"Tokens Fireworks{mock} : {usage['total_tokens']} "
          f"(prompt {usage['prompt_tokens']} / completion {usage['completion_tokens']}) "
          f"sur {usage['calls']} appels")
    print("Rappel leader actuel : 4 268 tokens à 84,2 %\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
