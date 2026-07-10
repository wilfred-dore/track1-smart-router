"""Zero-cost confidence gate: deterministic heuristics + local self-consistency.

score() returns a confidence in [0, 1]; the router compares it against the
per-category threshold from config.yaml to decide whether to keep the local
answer or escalate.
"""
import ast
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


def _non_latin_ratio(text):
    """Answers must be in English; small local models occasionally drift into
    other scripts (idea credit: my5757980/amd-hackathon-track1)."""
    if not text:
        return 0.0
    return sum(1 for ch in text if ord(ch) > 0x24F) / len(text)


_SENT_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def _requested_sentences(prompt):
    m = re.search(r"\b(?:in|exactly)\s+(one|two|three|four|five|\d+)\s+sentences?\b",
                  prompt.lower())
    if not m:
        return None
    return _SENT_WORDS.get(m.group(1)) or int(m.group(1))


def _fenced_code_parses(answer):
    """ast.parse a fenced Python block: broken code should escalate, not ship
    (idea credit: VisistaJayanti/AMD_Hackathon_Track1's deterministic validators).
    Returns None when there is no fenced block to check reliably."""
    m = re.search(r"```(?:python)?\s*\n?(.*?)```", answer, re.S)
    if not m or not m.group(1).strip():
        return None
    try:
        ast.parse(m.group(1))
        return True
    except SyntaxError:
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
    if _non_latin_ratio(a) > 0.15:  # responses must be in English
        s -= 0.5

    if category == "math":
        s += 0.2 if re.search(r"-?\d", a) else -0.5
    elif category == "sentiment":
        s += 0.2 if re.search(r"\b(positive|negative|neutral|mixed)\b", low) else -0.4
    elif category == "ner":
        s += 0.2 if re.search(r"\b(person|organi[sz]ation|location|date|org)\b", low) else -0.3
    elif category in ("code_debugging", "code_generation"):
        s += 0.2 if ("def " in a or "```" in a or "return" in a) else -0.4
        if _fenced_code_parses(a) is False:  # syntactically broken code
            s -= 0.35
    elif category == "summarization":
        limit = _requested_sentences(prompt)
        if limit and len(_sentences(a)) > limit:
            s -= 0.3
        if len(a) >= len(prompt):  # a summary longer than its source is suspect
            s -= 0.3
    elif category == "logic":
        names = set(re.findall(r"\b[A-Z][a-z]+\b", prompt)) - _STOP_NAMES
        s += 0.15 if any(n in a for n in names) else -0.3
    else:  # factual
        s += 0.1 if len(a.split()) >= 3 else -0.3
        # Multi-part questions are where a small local model fails silently
        # (wrong second half stated with full confidence): push toward escalation.
        if " and " in prompt.lower() or prompt.count("?") > 1:
            s -= 0.3
    return max(0.0, min(1.0, s))


def answer_key(answer, category):
    """Comparison key for self-consistency (the 'substance' of the answer)."""
    low = answer.lower()
    if category == "math":
        nums = re.findall(r"-?\d[\d,]*\.?\d*", low)
        return nums[-1].replace(",", "") if nums else low[:24]
    if category == "sentiment":
        m = re.search(r"\b(positive|negative|neutral|mixed)\b", low)
        return m.group(1) if m else low[:24]
    return re.sub(r"\W+", " ", low).strip()[:32]


def self_consistency_bonus(answer, category, resample, samples=2):
    """Resample locally (0 Fireworks tokens) and compare answer keys.

    All samples agree -> +0.2 ; disagreement -> -0.25 ; failure -> 0.
    """
    key = answer_key(answer, category)
    for _ in range(max(1, samples - 1)):
        other = resample()
        if other is None:
            return 0.0
        if answer_key(other, category) != key:
            return -0.25
    return 0.2
