"""Gate de confiance à coût nul : heuristiques déterministes + self-consistency locale.

score() retourne une confiance dans [0, 1] ; le routeur la compare au seuil
par catégorie de config.yaml pour décider de garder la réponse locale ou d'escalader.
"""
import re

_HEDGES = ("i don't know", "i do not know", "i cannot", "i can't", "as an ai",
           "i'm not sure", "i am not sure", "unable to")
_STOP_NAMES = {"Who", "What", "Which", "When", "Where", "Why", "How", "If", "The",
               "A", "An", "Each", "Three", "Two", "Four", "Five", "Find", "Solve"}


def _sentences(text):
    return [s for s in re.split(r"[.!?]+(?:\s|$)", text.strip()) if s.strip()]


def _degenerate(answer):
    words = answer.lower().split()
    if len(words) >= 12:
        grams = [" ".join(words[i:i + 4]) for i in range(len(words) - 3)]
        if max(grams.count(g) for g in set(grams)) >= 4:
            return True
    return False


def score(prompt, answer, category):
    if not answer or not answer.strip():
        return 0.0
    a = answer.strip()
    low = a.lower()
    if _degenerate(a):
        return 0.15
    s = 0.7
    if any(h in low for h in _HEDGES):
        s -= 0.4

    if category == "math":
        s += 0.2 if re.search(r"-?\d", a) else -0.5
    elif category == "sentiment":
        s += 0.2 if re.search(r"\b(positive|negative|neutral|mixed)\b", low) else -0.4
    elif category == "ner":
        s += 0.2 if re.search(r"\b(person|organi[sz]ation|location|date|org)\b", low) else -0.3
    elif category in ("code_debugging", "code_generation"):
        s += 0.2 if ("def " in a or "```" in a or "return" in a) else -0.4
    elif category == "summarization":
        if "one sentence" in prompt.lower() and len(_sentences(a)) > 1:
            s -= 0.3
        if len(a) >= len(prompt):  # résumé plus long que la source : suspect
            s -= 0.3
    elif category == "logic":
        names = set(re.findall(r"\b[A-Z][a-z]+\b", prompt)) - _STOP_NAMES
        s += 0.15 if any(n in a for n in names) else -0.3
    else:  # factual
        s += 0.1 if len(a.split()) >= 3 else -0.3
    return max(0.0, min(1.0, s))


def answer_key(answer, category):
    """Clé de comparaison pour la self-consistency (la 'substance' de la réponse)."""
    low = answer.lower()
    if category == "math":
        nums = re.findall(r"-?\d[\d,]*\.?\d*", low)
        return nums[-1].replace(",", "") if nums else low[:24]
    if category == "sentiment":
        m = re.search(r"\b(positive|negative|neutral|mixed)\b", low)
        return m.group(1) if m else low[:24]
    return re.sub(r"\W+", " ", low).strip()[:32]


def self_consistency_bonus(answer, category, resample, samples=2):
    """Re-échantillonne localement (0 token Fireworks) et compare les clés.

    Accord de tous les échantillons -> +0.2 ; désaccord -> -0.25 ; échec -> 0.
    """
    key = answer_key(answer, category)
    for _ in range(max(1, samples - 1)):
        other = resample()
        if other is None:
            return 0.0
        if answer_key(other, category) != key:
            return -0.25
    return 0.2
