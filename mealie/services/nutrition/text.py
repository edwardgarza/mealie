import re
import unicodedata

_WORD = re.compile(r"[a-z0-9]+")


def stem(word: str) -> str:
    """A deliberately small singulariser; both sides of every comparison go through it."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("oes"):
        return word[:-2]
    if len(word) > 4 and word.endswith("ves"):
        return word[:-3] + "f"
    if len(word) > 4 and word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return [stem(word) for word in _WORD.findall(folded)]
