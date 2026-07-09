"""Client Fireworks (API OpenAI-compatible) + mock qui compte les tokens.

Le mode est choisi par la variable d'env FIREWORKS_MODE :
  - mock : aucune requête réseau, réponses simulées, tokens comptés (estimation)
  - live : appels réels via FIREWORKS_BASE_URL / FIREWORKS_API_KEY
  - auto (défaut) : live si FIREWORKS_API_KEY est présent, sinon mock
    -> à l'évaluation le harness injecte la clé, donc auto => live sans changement de code.
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
    """Réponse exploitable d'un message OpenAI-compatible, y compris pour les
    modèles 'reasoning' (minimax-m3, gemma4...) : retire les blocs <think> inline
    et, si le contenu final est vide (raisonnement coupé par max_tokens), récupère
    la dernière ligne utile du champ reasoning plutôt que de ne rien répondre."""
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

    def chat(self, model, messages, max_tokens, stop=None):
        prompt_toks = sum(approx_tokens(m["content"]) for m in messages)
        completion_toks = max(1, math.ceil(max_tokens * self.completion_ratio))
        usage = self._record(prompt_toks, completion_toks)
        return f"[MOCK:{model}] simulated escalation answer", usage


class FireworksClient(_UsageTracker):
    is_mock = False

    def __init__(self):
        super().__init__()
        from openai import OpenAI  # import paresseux : inutile en mode mock
        self._client = OpenAI(base_url=os.environ["FIREWORKS_BASE_URL"],
                              api_key=os.environ["FIREWORKS_API_KEY"])

    def chat(self, model, messages, max_tokens, stop=None):
        resp = self._client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens,
            stop=stop or None, temperature=0)
        text = extract_text(resp.choices[0].message)
        if resp.usage:
            usage = self._record(resp.usage.prompt_tokens, resp.usage.completion_tokens)
        else:  # estimation de repli si le proxy ne renvoie pas l'usage
            usage = self._record(sum(approx_tokens(m["content"]) for m in messages),
                                 approx_tokens(text))
        return text, usage


def get_client(cfg):
    mode = os.environ.get("FIREWORKS_MODE", "auto").lower()
    if mode == "auto":
        mode = "live" if os.environ.get("FIREWORKS_API_KEY") else "mock"
    if mode == "live":
        return FireworksClient()
    print("[fireworks] MODE MOCK : aucun appel réseau, tokens simulés", file=sys.stderr)
    return MockFireworksClient(cfg["mock"]["completion_ratio"])


def resolve_model(category, cfg):
    """Choisit un modèle dans ALLOWED_MODELS (env, jamais en dur) selon les
    préférences par catégorie de config.yaml (matching par sous-chaîne)."""
    allowed = [m.strip() for m in os.environ.get("ALLOWED_MODELS", "").split(",") if m.strip()]
    prefs = by_category(cfg["escalation"]["model_preference"], category) or []
    for pref in prefs:
        for model in allowed:
            if pref.lower() in model.lower():
                return model
    if allowed:
        return allowed[0]
    return "mock-model"  # uniquement atteignable en mode mock
