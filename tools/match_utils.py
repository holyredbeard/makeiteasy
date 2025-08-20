import re
from difflib import SequenceMatcher


def normalize(text: str) -> str:
    if not text:
        return ""
    t = text.strip().lower()
    # remove parentheses content
    t = re.sub(r"\([^\)]*\)", "", t)
    # collapse spaces
    t = re.sub(r"\s+", " ", t)
    return t


def singularize(word: str) -> str:
    w = normalize(word)
    # naive singularization for english terms
    if w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith("sses") or w.endswith("shes") or w.endswith("ches"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def ratio(a: str, b: str) -> float:
    a_n = normalize(a)
    b_n = normalize(b)
    return SequenceMatcher(None, a_n, b_n).ratio()


def best_match(query: str, candidates: list[str]) -> tuple[str, float]:
    best = ("", 0.0)
    for c in candidates:
        r = ratio(query, c)
        if r > best[1]:
            best = (c, r)
    return best


