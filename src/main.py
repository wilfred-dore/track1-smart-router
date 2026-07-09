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
    results = []
    for task in tasks:
        try:
            rec = router.solve(task)
        except Exception as e:
            print(f"[main] task {task.get('task_id')} failed: {e}", file=sys.stderr)
            rec = {"task_id": task.get("task_id"), "answer": "Unable to answer.",
                   "route": "error", "tokens": 0}
        results.append({"task_id": rec["task_id"], "answer": rec["answer"]})
        print(f"[main] {rec['task_id']}: route={rec.get('route')} "
              f"tokens={rec.get('tokens', 0)}", file=sys.stderr)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    os.replace(tmp_path, output_path)

    usage = router.fw.usage_summary()
    print(f"[main] {len(results)} answers written to {output_path} "
          f"in {time.time() - t0:.1f}s — Fireworks: {usage['calls']} calls, "
          f"{usage['total_tokens']} tokens{' (MOCK)' if router.fw.is_mock else ''}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
