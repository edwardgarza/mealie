import re
from dataclasses import dataclass

from .text import tokens

ML_PER_UNIT: dict[str, float] = {
    "teaspoon": 4.92892,
    "tablespoon": 14.7868,
    "fluid_ounce": 29.5735,
    "cup": 236.588,
    "pint": 473.176,
    "quart": 946.353,
    "milliliter": 1.0,
    "liter": 1000.0,
}

_VOLUME_WORDS: dict[str, str] = {
    "tsp": "teaspoon",
    "teaspoon": "teaspoon",
    "teaspoons": "teaspoon",
    "tbsp": "tablespoon",
    "tablespoon": "tablespoon",
    "tablespoons": "tablespoon",
    "fl oz": "fluid_ounce",
    "floz": "fluid_ounce",
    "fluid ounce": "fluid_ounce",
    "cup": "cup",
    "cups": "cup",
    "c": "cup",
    "pint": "pint",
    "quart": "quart",
    "ml": "milliliter",
    "milliliter": "milliliter",
    "l": "liter",
    "liter": "liter",
}
_WEIGHT_WORDS = {"oz", "lb", "g", "kg", "gram", "grams", "ounce", "pound"}
_VOLUME_RE = re.compile(
    r"^(" + "|".join(sorted((re.escape(w) for w in _VOLUME_WORDS), key=len, reverse=True)) + r")\b[\s,]*(.*)$"
)


@dataclass(frozen=True, slots=True)
class Portion:
    """A household measure of one food: `amount` of `text` weighs `grams`.

    `text` is free-form, as published: "cup, chopped", "medium (2-1/2\" dia)", "clove".
    """

    amount: float
    text: str
    grams: float


@dataclass(frozen=True, slots=True)
class ParsedPortion:
    kind: str
    """"volume", "count" or "weight\""""
    unit: str
    """Canonical volume unit, or the leading label of a count portion ("medium", "clove", "slice")"""
    label: frozenset[str]
    qualifier: frozenset[str]
    grams_per_unit: float
    source: Portion

    @property
    def grams_per_ml(self) -> float:
        return self.grams_per_unit / ML_PER_UNIT[self.unit]


def parse_portion(portion: Portion) -> ParsedPortion | None:
    text = portion.text.strip().lower()
    if not text or portion.amount <= 0 or portion.grams <= 0:
        return None

    per_unit = portion.grams / portion.amount
    volume = _VOLUME_RE.match(text)
    if volume:
        qualifier = frozenset(tokens(volume.group(2)))
        return ParsedPortion("volume", _VOLUME_WORDS[volume.group(1)], frozenset(), qualifier, per_unit, portion)

    head, _, rest = re.sub(r"\(.*?\)", lambda m: "," + m.group(0), text, count=1).partition(",")
    label = tokens(head)
    if not label:
        return None
    if label[0] in _WEIGHT_WORDS:
        return ParsedPortion("weight", label[0], frozenset(), frozenset(), per_unit, portion)
    return ParsedPortion("count", " ".join(label), frozenset(label), frozenset(tokens(rest)), per_unit, portion)
