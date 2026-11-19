import json
from dataclasses import dataclass, field
from functools import lru_cache

from .dataset import DATA_DIR, FoodRecord, NutritionDataset, SearchHit
from .portions import Portion
from .text import tokens

_GRAMS = {"g": 1.0, "kg": 1000.0, "oz": 28.3495, "lb": 453.592}
_CURATED_UNIT_TEXT = {"c": "cup", "tsp": "tsp", "tbsp": "tbsp", "floz": "fl oz", "pcs": "each", "ml": "ml", "l": "l"}


def _t(text: str) -> frozenset[str]:
    return frozenset(tokens(text))


# Kitchen wording -> the wording food databases use. Each entry replaces the trigger words; the
# last word of a replacement is its head noun.
REWRITES: list[tuple[frozenset[str], list[str]]] = [
    (_t("unsalted"), tokens("without salt")),
    (_t("confectioners sugar"), tokens("powdered sugar")),
    (_t("icing sugar"), tokens("powdered sugar")),
    (_t("scallion"), tokens("spring scallions onion")),
    (_t("green onion"), tokens("spring scallions onion")),
    (_t("cilantro"), tokens("cilantro leaves coriander")),
    (_t("heavy cream"), tokens("heavy whipping cream")),
    (_t("half and half"), tokens("half and cream")),
    (_t("extra virgin"), []),
    (_t("fresh"), []),
    (_t("freshly"), []),
    (_t("organic"), []),
    (_t("ripened"), []),
    (_t("kosher"), []),
    (_t("sea salt"), tokens("table salt")),
    (_t("cracked pepper"), tokens("black pepper")),
    (_t("red pepper flakes"), tokens("red cayenne pepper")),
    (_t("bell pepper"), tokens("sweet pepper")),
    (_t("stock"), tokens("broth")),
    (_t("garbanzo"), tokens("chickpea")),
    (_t("chicken breast"), tokens("breast meat only chicken")),
    (_t("chicken thigh"), tokens("thigh meat only chicken")),
]

# What a recipe most likely means when it names a food with no variety. These are judgment calls;
# links made through one are reported as "assumed" so the user can correct them.
DEFAULT_VARIETY: dict[frozenset[str], list[str]] = {
    _t("milk"): tokens("whole milk"),
    _t("egg"): tokens("whole raw fresh egg"),
    _t("bacon"): tokens("cured bacon pork"),
    _t("bread"): tokens("white commercially prepared bread"),
    _t("butter"): tokens("salted butter"),
    _t("flour"): tokens("all purpose flour"),
    _t("sugar"): tokens("granulated sugar"),
    _t("salt"): tokens("table salt"),
    _t("pepper"): tokens("black pepper"),
    _t("rice"): tokens("white long grain rice"),
    _t("onion"): tokens("yellow onion"),
    _t("oil"): tokens("soybean salad cooking oil"),
    _t("vegetable oil"): tokens("soybean salad cooking oil"),
    _t("cream"): tokens("heavy whipping cream"),
    _t("tomato"): tokens("red ripe year round average tomato"),
}

# Words that never name the food; they must not become the head noun of a search
_STOPWORDS = frozenset({"in", "and", "or", "of", "with", "the", "a", "an", "for", "to", "from"})


@dataclass(slots=True)
class CuratedFood:
    slug: str
    name: str
    fdc_id: int | None
    nutrients: dict[str, float]
    portions: tuple[Portion, ...]
    token_sets: tuple[frozenset[str], ...]


@dataclass(slots=True)
class FoodLink:
    record: FoodRecord | None
    method: str
    """manual | curated | curated_macros | search | search_weak | none"""
    assumed_default: bool = False
    matched_on: str = ""
    extra_portions: tuple[Portion, ...] = ()
    suggestions: list[SearchHit] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.record is None or self.method in ("search_weak", "curated_macros") or self.assumed_default

    @property
    def portions(self) -> tuple[Portion, ...]:
        # curated household measures first: a person chose them for this exact food
        return self.extra_portions + (self.record.portions if self.record else ())


def _curated_portions(conversions: list[list]) -> tuple[Portion, ...]:
    portions = []
    for base_amount, base_unit, converted_amount, converted_unit in conversions:
        if converted_unit in _GRAMS and base_unit in _CURATED_UNIT_TEXT:
            portions.append(
                Portion(base_amount, _CURATED_UNIT_TEXT[base_unit], converted_amount * _GRAMS[converted_unit])
            )
        elif base_unit in _GRAMS and converted_unit in _CURATED_UNIT_TEXT:
            portions.append(
                Portion(converted_amount, _CURATED_UNIT_TEXT[converted_unit], base_amount * _GRAMS[base_unit])
            )
    return tuple(portions)


@lru_cache(maxsize=1)
def load_curated() -> tuple[CuratedFood, ...]:
    raw = json.loads((DATA_DIR / "curated_foods.json").read_text(encoding="utf-8"))
    return tuple(
        CuratedFood(
            slug=item["slug"],
            name=item["name"],
            fdc_id=item["fdc_id"],
            nutrients=item["n"],
            portions=_curated_portions(item["conversions"]),
            token_sets=tuple({_t(item["name"]), _t(item["plural_name"])} - {frozenset()}),
        )
        for item in raw
    )


def _rewrite(query: list[str]) -> list[str]:
    for trigger, replacement in REWRITES:
        if trigger <= set(query):
            remaining = [t for t in query if t not in trigger]
            head_replaced = query[-1] in trigger
            query = (remaining + replacement) if head_replaced else (replacement + remaining)
    return query


_MACROS = ("protein_g", "fat_g", "carbohydrate_g")


def _macro_distance(reference: dict[str, float], other: dict[str, float]) -> float | None:
    """How far apart two foods are per 100 g, or None when they are not plausibly the same food."""
    if "energy_kcal" not in reference or "energy_kcal" not in other:
        return None
    energy_gap = abs(reference["energy_kcal"] - other["energy_kcal"])
    if energy_gap > max(20.0, 0.15 * reference["energy_kcal"]):
        return None
    distance = energy_gap / max(reference["energy_kcal"], 50.0)
    for key in _MACROS:
        if key in reference and key in other:
            gap = abs(reference[key] - other[key])
            if gap > max(3.0, 0.2 * reference[key]):
                return None
            distance += gap / 100
    return distance


def _agrees(reference: dict[str, float], other: dict[str, float]) -> bool:
    return _macro_distance(reference, other) is not None


def _name_query(name: str) -> list[str]:
    """Search tokens for a database-style name: "Butter, stick, unsalted" -> stick unsalted butter."""
    lead, _, rest = name.partition(",")
    return tokens(rest) + tokens(lead)


class FoodMatcher:
    def __init__(self, dataset: NutritionDataset | None = None) -> None:
        self.dataset = dataset or NutritionDataset.load()
        self.curated = load_curated()

    def link(self, name: str, other_names: tuple[str, ...] = ()) -> FoodLink:
        """Propose a database entry for one food, trying its name, then its plural and aliases."""
        best: FoodLink | None = None
        for candidate in (name, *other_names):
            link = self._link_one(candidate)
            if link.record and not link.needs_review:
                return link
            if best is None or (link.record and not best.record):
                best = link
        return best or FoodLink(None, "none")

    def manual(self, record_id: str, name: str, other_names: tuple[str, ...] = ()) -> FoodLink | None:
        """The link for a food whose database entry a user chose. None if the entry is unknown."""
        record = self.dataset.get(int(record_id)) if record_id.isdigit() else None
        if record is None:
            return None
        # keep offering what automatic matching would have picked, to make switching back easy
        automatic = self.link(name, other_names)
        return FoodLink(record, "manual", matched_on=record.name, suggestions=automatic.suggestions)

    def search_text(self, text: str, limit: int = 20) -> list[SearchHit]:
        """Candidates for text typed into the food picker"""
        return self.dataset.search_text(_rewrite(tokens(text)), limit)

    def _search(self, query: list[str], limit: int = 15) -> list[SearchHit]:
        while query and query[-1] in _STOPWORDS:
            query = query[:-1]
        hits = self.dataset.search(query, limit)
        if not hits and len(query) > 1:
            # the last word was not a food ("bay leaf", "soy sauce low sodium"); try the others as head
            for i in range(len(query) - 2, -1, -1):
                if query[i] in _STOPWORDS:
                    continue
                hits = self.dataset.search(query[:i] + query[i + 1 :] + [query[i]], limit)
                if hits:
                    break
        return hits

    def _link_one(self, name: str) -> FoodLink:
        query = tokens(name)
        if not query:
            return FoodLink(None, "none")

        assumed = False
        if frozenset(query) in DEFAULT_VARIETY:
            query, assumed = DEFAULT_VARIETY[frozenset(query)], True

        rewritten = _rewrite(query)
        hits = self._search(rewritten)
        curated = self._find_curated(frozenset(query)) or self._find_curated(frozenset(rewritten))
        if curated:
            link = self._from_curated(curated, hits, assumed)
            if link:
                return link
        if not hits:
            return FoodLink(None, "none")

        top = hits[0]
        record, donors = self._prefer_sr_legacy(top.record, hits)
        return FoodLink(
            record,
            "search" if top.confident else "search_weak",
            assumed_default=assumed,
            matched_on=record.name,
            extra_portions=donors,
            suggestions=hits[:5],
        )

    def _prefer_sr_legacy(self, record: FoodRecord, hits: list[SearchHit]) -> tuple[FoodRecord, tuple[Portion, ...]]:
        """Swap a Foundation record for the same food in SR Legacy, which has the full nutrient list
        and household measures. Returns the record to use and any portions worth keeping."""
        if record.source != "foundation":
            return record, ()
        twins = [*self._search(_rewrite(_name_query(record.name))), *hits]
        for hit in sorted(twins, key=lambda h: -h.score):
            if (
                hit.record.source == "sr_legacy"
                and hit.coverage >= 0.5
                and _agrees(record.nutrients, hit.record.nutrients)
            ):
                return hit.record, record.portions
        return record, ()

    def _find_curated(self, query: frozenset[str]) -> CuratedFood | None:
        exact = [c for c in self.curated if query in c.token_sets]
        if exact:
            return exact[0]
        # "all purpose flour" -> "Unbleached All-Purpose Flour", only when nothing else fits
        near = [c for c in self.curated if any(query < ts and len(ts - query) == 1 for ts in c.token_sets)]
        return near[0] if len(near) == 1 and len(query) > 1 else None

    def _from_curated(self, curated: CuratedFood, hits: list[SearchHit], assumed: bool) -> FoodLink | None:
        """A person already chose the variety; find the fullest database record that agrees with it.

        Returns None when the curated entry gives nothing to go on, so the caller falls back to search.
        """
        by_id = self.dataset.get(curated.fdc_id) if curated.fdc_id else None
        if by_id:
            record, donors = self._prefer_sr_legacy(by_id, hits)
            return FoodLink(
                record, "curated", assumed, f"{curated.name} -> {record.name}", curated.portions + donors, hits[:5]
            )

        # The curated id points at a USDA dataset that is not bundled. Some of those entries carry
        # no values of their own (all zero, or no energy), and then there is nothing to check a
        # search result against.
        if curated.nutrients.get("energy_kcal", 0) <= 0:
            return None

        named = [*self._search(_rewrite(tokens(curated.name))), *hits]
        for hit in sorted(named, key=lambda h: (h.record.source != "sr_legacy", -h.score)):
            if hit.coverage >= 0.5 and _agrees(curated.nutrients, hit.record.nutrients):
                return FoodLink(
                    hit.record, "curated", assumed, f"{curated.name} ~> {hit.record.name}", curated.portions, hits[:5]
                )
        record = FoodRecord(f"curated:{curated.slug}", "curated", curated.name, "", curated.nutrients)
        return FoodLink(record, "curated_macros", assumed, curated.name, curated.portions, hits[:5])
