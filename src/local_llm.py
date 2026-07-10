"""llama-cpp-python wrapper (GGUF 2-3B 4-bit quantized, CPU-only).

Degrades gracefully: if llama-cpp-python or the model file is missing,
generate() returns None and the router moves on to the next stage (escalation).
"""
import os
import sys

from .config import by_category


def available_cpus():
    """Docker CPU quotas lie to os.cpu_count(): a 2-vCPU cgroup on a 32-core
    host reports 32 cores, and llama.cpp thrashes with 16x too many threads.
    Read the cgroup v2 quota when present (credit: Anbu-00001/Minimalist
    documented this exact failure mode)."""
    try:
        with open("/sys/fs/cgroup/cpu.max", encoding="ascii") as f:
            quota, period = f.read().split()[:2]
        if quota != "max":
            return max(1, int(int(quota) / int(period)))
    except Exception:
        pass
    return os.cpu_count() or 2


class LocalLLM:
    def __init__(self, cfg):
        self.cfg = cfg["local"]
        self._llm = None
        self.available = False
        path = self.cfg["model_path"]
        try:
            from llama_cpp import Llama
        except Exception as e:
            # Not just ImportError: a broken native lib raises RuntimeError/OSError.
            # The container must degrade to full escalation, never crash.
            print(f"[local_llm] llama-cpp-python unavailable ({e.__class__.__name__}: {e}): "
                  "local inference disabled", file=sys.stderr)
            return
        if not os.path.exists(path):
            print(f"[local_llm] model not found ({path}): local inference disabled",
                  file=sys.stderr)
            return
        n_threads = self.cfg.get("n_threads") or available_cpus()
        try:
            self._llm = Llama(model_path=path, n_ctx=self.cfg["n_ctx"],
                              n_threads=n_threads, verbose=False)
            self.available = True
            print(f"[local_llm] model loaded: {path} ({n_threads} threads)", file=sys.stderr)
        except Exception as e:
            print(f"[local_llm] model load failed: {e}", file=sys.stderr)

    def generate(self, prompt, category, temperature=None):
        if not self.available:
            return None
        hint = (self.cfg.get("category_hints") or {}).get(category, "")
        system = self.cfg["system_prompt"] + (" " + hint if hint else "")
        try:
            out = self._llm.create_chat_completion(
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompt}],
                max_tokens=by_category(self.cfg["max_tokens"], category),
                temperature=self.cfg["temperature"] if temperature is None else temperature,
            )
            text = (out["choices"][0]["message"]["content"] or "").strip()
            return text or None
        except Exception as e:
            print(f"[local_llm] generation failed: {e}", file=sys.stderr)
            return None
