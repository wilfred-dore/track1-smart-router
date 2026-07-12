"""Entry point: reads /input/tasks.json, writes /output/results.json.

Exact formats from the Participant Guide:
  input  : [ { "task_id": "...", "prompt": "..." }, ... ]
  output : [ { "task_id": "...", "answer": "..." }, ... ]
Exit code 0 on success, non-zero on failure. An answer is always written for
every task_id, even if an individual task fails.
"""
import json
import os
import sys
import time

from .config import load_config, load_dotenv
from .fireworks import get_client
from .local_llm import LocalLLM
from .router import Router


def main():
    t0 = time.time()
    load_dotenv()
    cfg = load_config()
    input_path = cfg["io"]["input_path"]
    output_path = cfg["io"]["output_path"]

    try:
        with open(input_path, encoding="utf-8") as f:
            tasks = json.load(f)
    except Exception as e:
        print(f"[main] cannot read {input_path}: {e}", file=sys.stderr)
        return 1

    router = Router(cfg, LocalLLM(cfg), get_client(cfg))

    def write_results(results):
        # Rewritten atomically after every task so /output/results.json is valid
        # at any kill point — a hard timeout no longer scores zero
        # (pattern credit: Kunsh162007/Hybrid-token-efficient-routing-agent).
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        tmp_path = output_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
        os.replace(tmp_path, output_path)

    results = []

    def on_result(rec):
        # Upsert by task_id: the batched path emits a provisional local answer
        # first, then the improved escalated answer for the same task, so the
        # output file is complete (not just solver tasks) at any kill point.
        entry = {"task_id": rec["task_id"], "answer": rec["answer"]}
        for i, existing in enumerate(results):
            if existing["task_id"] == rec["task_id"]:
                results[i] = entry
                break
        else:
            results.append(entry)
        write_results(results)
        print(f"[main] {rec['task_id']}: route={rec.get('route')} "
              f"tokens={rec.get('tokens', 0)}", file=sys.stderr)

    router.solve_all(tasks, on_result=on_result)

    usage = router.fw.usage_summary()
    print(f"[main] {len(results)} answers written to {output_path} "
          f"in {time.time() - t0:.1f}s — Fireworks: {usage['calls']} calls, "
          f"{usage['total_tokens']} tokens{' (MOCK)' if router.fw.is_mock else ''}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
