import gzip
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .portions import Portion
from .text import tokens

DATA_DIR = Path(__file__).parent / "data"

# Categories that hold finished products rather than ingredients; a cook writing "onion" does not
# mean one of these, so they only win when nothing else matches.
_PRODUCT_CATEGORIES = {
    "Baby Foods",
    "Fast Foods",
    "Restaurant Foods",
    "Meals, Entrees, and Side Dishes",
    "Snacks",
    "American Indian/Alaska Native Foods",
    "Breakfast Cereals",
}
_PROCESSED = {
    "cooked", "boiled", "fried", "roasted", "baked", "canned", "frozen", "dried", "dehydrated", "breaded",
    "microwaved", "stewed", "braised", "grilled", "heated", "prepared", "mix", "toasted", "pickled", "smoked",
    "drained", "sweetened", "imitation", "substitute", "low", "reduced", "nonfat", "free", "fortified",
    "powder", "flake", "juice", "sauce", "soup", "oil", "bread", "flavor", "dry", "cube", "cubed",
    "concentrate", "condensed", "meatless", "tofu", "vegetarian", "analog",
}  # fmt: skip
# First segments that name a food group rather than the food: "Spices, cinnamon, ground" is cinnamon
_CATEGORY_LEADS = {
    frozenset(tokens(lead))
    for lead in (
        "spices", "cheese", "oil", "nuts", "seeds", "fish", "beans", "leavening agents", "soup", "sauce",
        "beverages", "alcoholic beverage", "candies", "vinegar", "crustaceans", "mollusks", "cereals",
        "vegetable oil", "syrups", "sweeteners", "peppers", "lettuce", "squash", "mushrooms", "cabbage",
    )
}  # fmt: skip
_BRAND = re.compile(r"\b[A-Z][A-Z'&.-]{2,}\b")


@dataclass(slots=True)
class FoodRecord:
    id: int | str
    source: str
    name: str
    category: str
    nutrients: dict[str, float]
    """Amount per 100 g, keyed by Mealie nutrient key"""
    portions: tuple[Portion, ...] = ()
    segments: tuple[frozenset[str], ...] = field(default=(), repr=False)
    all_tokens: frozenset[str] = field(default=frozenset(), repr=False)

    def __post_init__(self) -> None:
        if not self.segments:
            self.segments = tuple(frozenset(tokens(part)) for part in self.name.split(","))
            self.all_tokens = frozenset().union(*self.segments)


@dataclass(frozen=True, slots=True)
class SearchHit:
    record: FoodRecord
    score: float
    coverage: float
    confident: bool
    """Every query word was found and the head noun leads the name; safe to pre-select."""


class NutritionDataset:
    def __init__(self, records: list[FoodRecord]) -> None:
        self.records = records
        self._by_id = {record.id: record for record in records}
        self._index: dict[str, list[FoodRecord]] = defaultdict(list)
        for record in records:
            for token in record.all_tokens:
                self._index[token].append(record)

    @classmethod
    @lru_cache(maxsize=1)
    def load(cls) -> NutritionDataset:
        with gzip.open(DATA_DIR / "usda_foods.json.gz", "rt", encoding="utf-8") as f:
            raw = json.load(f)
        return cls(
            [
                FoodRecord(
                    id=item["id"],
                    source=item["src"],
                    name=item["name"],
                    category=item["cat"],
                    nutrients=item["n"],
                    portions=tuple(Portion(*portion) for portion in item["p"]),
                )
                for item in raw
            ]
        )

    def get(self, record_id: int | str) -> FoodRecord | None:
        return self._by_id.get(record_id)

    def search(self, query_tokens: list[str], limit: int = 5) -> list[SearchHit]:
        """Rank foods for a query given as stemmed tokens, head noun last ("unsalt butter")."""
        if not query_tokens:
            return []

        query = set(query_tokens)
        head = query_tokens[-1]
        hits: list[SearchHit] = []
        for record in self._index.get(head, []):
            hits.append(self._score(record, query, head))

        hits.sort(key=lambda hit: (-hit.score, len(hit.record.name)))
        return hits[:limit]

    def search_text(self, query_tokens: list[str], limit: int = 20) -> list[SearchHit]:
        """Rank foods for text a person typed, where any word may be the food and the last word
        may still be half written."""
        if not query_tokens:
            return []

        *complete, last = query_tokens
        # "cook" must also find "cooked", even though "cook" is a word of its own
        last_words = [word for word in self._index if word.startswith(last)]
        if not last_words:
            return []

        candidates: dict[int | str, FoodRecord] = {}
        for word in last_words:
            for record in self._index[word]:
                if all(token in record.all_tokens for token in complete):
                    candidates[record.id] = record

        hits = []
        for record in candidates.values():
            # the typed prefix stands for whichever full word this record has
            words = complete + [next(w for w in last_words if w in record.all_tokens)]
            hits.append(max((self._score(record, set(words), head) for head in words), key=lambda hit: hit.score))
        hits.sort(key=lambda hit: (-hit.score, len(hit.record.name)))
        return hits[:limit]

    @staticmethod
    def _score(record: FoodRecord, query: set[str], head: str) -> SearchHit:
        matched = query & record.all_tokens
        coverage = len(matched) / len(query)
        lead = record.segments[0]
        second = record.segments[1] if len(record.segments) > 1 else frozenset()
        # USDA names run "Onions, raw" or "Spices, pepper, black": the food itself is the first
        # segment, or the second when the first only names a food group.
        food = second if (lead in _CATEGORY_LEADS and second) else lead

        score = 10 * coverage
        if head in food or head in lead:
            score += 4
        elif head in second:
            score += 2.5
        score += len(matched & lead) + 0.5 * len(matched & second)
        if food <= query or lead <= query:
            score += 3

        extra = record.all_tokens - query
        if "raw" in extra:
            score += 1.5
        score -= 1.5 * min(len(extra & _PROCESSED), 3)
        score -= 0.25 * min(len(extra), 12)
        if _BRAND.search(record.name):
            score -= 4
        if record.category in _PRODUCT_CATEGORIES:
            score -= 5

        confident = coverage == 1 and (head in lead or head in food)
        return SearchHit(record, round(score, 2), coverage, confident)
