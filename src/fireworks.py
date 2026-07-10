"""Fireworks client (OpenAI-compatible API) + token-counting mock.

The mode is selected by the FIREWORKS_MODE env var:
  - mock : no network calls, simulated answers, tokens counted (estimate)
  - live : real calls through FIREWORKS_BASE_URL / FIREWORKS_API_KEY
  - auto (default) : live if FIREWORKS_API_KEY is present, otherwise mock
    -> at evaluation time the harness injects the key, so auto => live
       with no code change.
"""
import math
import os
import re
import sys

from .config import by_category


def approx_tokens(text):
    return max(1, math.ceil(len(text) / 4))


_THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.S)


def extract_text(message):
    """Usable answer from an OpenAI-compatible message, including reasoning
    models (minimax-m3, gemma4...): strips inline <think> blocks and, when the
    final content is empty (reasoning cut off by max_tokens), falls back to the
    last useful line of the reasoning field rather than answering nothing."""
    content = _THINK_RE.sub("", (message.content or "")).strip()
    if content:
        return content
    reasoning = (getattr(message, "reasoning", None)
                 or getattr(message, "reasoning_content", None))
    if reasoning:
        lines = [l.strip() for l in str(reasoning).splitlines() if l.strip()]
        if lines:
            return lines[-1]
    return ""


class _UsageTracker:
    def __init__(self):
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def _record(self, prompt_tokens, completion_tokens):
        self.calls += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        return {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}

    def usage_summary(self):
        return {"calls": self.calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.prompt_tokens + self.completion_tokens}


class MockFireworksClient(_UsageTracker):
    is_mock = True

    def __init__(self, completion_ratio=0.6):
        super().__init__()
        self.completion_ratio = completion_ratio

    def chat(self, model, messages, max_tokens, stop=None, extra_params=None,
             timeout=None):
        prompt_toks = sum(approx_tokens(m["content"]) for m in messages)
        completion_toks = max(1, math.ceil(max_tokens * self.completion_ratio))
        usage = self._record(prompt_toks, completion_toks)
        return f"[MOCK:{model}] simulated escalation answer", usage


class FireworksClient(_UsageTracker):
    is_mock = False

    def __init__(self):
        super().__init__()
        from openai import OpenAI  # lazy import: not needed in mock mode
        self._client = OpenAI(base_url=os.environ["FIREWORKS_BASE_URL"],
                              api_key=os.environ.get("FIREWORKS_API_KEY") or "not-provided",
                              timeout=25.0)  # per-request rule is 30 s

    def chat(self, model, messages, max_tokens, stop=None, extra_params=None,
             timeout=None):
        client = self._client if timeout is None else self._client.with_options(timeout=timeout)
        resp = client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens,
            stop=stop or None, temperature=0,
            extra_body=extra_params or None)
        text = extract_text(resp.choices[0].message)
        if resp.usage:
            usage = self._record(resp.usage.prompt_tokens, resp.usage.completion_tokens)
        else:  # fallback estimate if the proxy does not return usage
            usage = self._record(sum(approx_tokens(m["content"]) for m in messages),
                                 approx_tokens(text))
        return text, usage


def get_client(cfg):
    mode = os.environ.get("FIREWORKS_MODE", "auto").lower()
    if mode == "auto":
        # Live as soon as the harness injected ANY Fireworks env: shipping mock
        # answers at grading time would be catastrophic even if only the key
        # is missing or renamed.
        mode = ("live" if (os.environ.get("FIREWORKS_API_KEY")
                           or os.environ.get("FIREWORKS_BASE_URL")) else "mock")
    if mode == "live":
        return FireworksClient()
    print("[fireworks] MOCK MODE: no network calls, simulated tokens", file=sys.stderr)
    return MockFireworksClient(cfg["mock"]["completion_ratio"])


def parse_allowed_models(raw):
    """Defensive parsing of ALLOWED_MODELS: harness formats vary (plain CSV,
    JSON-ish arrays, quotes, stray whitespace). A model name sent with a stray
    bracket or quote is an instant MODEL_VIOLATION."""
    cleaned = []
    for part in re.split(r"[,;\n]", raw or ""):
        model = part.strip().strip("[]\"' \t")
        if model:
            cleaned.append(model)
    return cleaned


def resolve_model(category, cfg):
    """Pick a model from ALLOWED_MODELS (env, never hardcoded) using the
    per-category preferences from config.yaml (substring matching)."""
    allowed = parse_allowed_models(os.environ.get("ALLOWED_MODELS", ""))
    prefs = by_category(cfg["escalation"]["model_preference"], category) or []
    for pref in prefs:
        for model in allowed:
            if pref.lower() in model.lower():
                return model
    if allowed:
        return allowed[0]
    return "mock-model"  # only reachable in mock mode
