from dataclasses import dataclass, field

from .matching import FoodLink
from .nutrients import NUTRIENT_KEYS
from .portions import ML_PER_UNIT, ParsedPortion, Portion, parse_portion
from .text import tokens

# Mealie's standardized units (see StandardizedUnitType). The Mealie integration should go through
# UnitConverter instead; the figures are the same ones pint uses.
_STANDARD_GRAMS = {"gram": 1.0, "kilogram": 1000.0, "ounce": 28.3495, "pound": 453.592}
_STANDARD_ML = {"milliliter": 1.0, "liter": 1000.0, "cup": 236.588, "fluid_ounce": 29.5735}
# Units too small to standardize, but which are still a volume
_TINY_ML = {"pinch": 0.31, "dash": 0.62}
_GENERIC_COUNT_UNITS = {"each", "piece", "whole", "item", "unit", "count", "pc", "ea"}
_SIZES = ("extra large", "jumbo", "large", "medium", "small")
_COUNT_FALLBACK = ("each", "medium", "whole", "item", "unit", "fruit", "piece", "large", "small")


@dataclass(frozen=True, slots=True)
class UnitInfo:
    name: str
    standard_quantity: float | None = None
    standard_unit: str | None = None


@dataclass(frozen=True, slots=True)
class IngredientInput:
    quantity: float | None
    unit: UnitInfo | None
    food_name: str | None
    context: str = ""
    """Free text around the ingredient (note, original line); picks "chopped" over "sliced\""""


@dataclass(slots=True)
class IngredientResult:
    status: str
    """ok | weak_match | no_food | no_link | no_quantity | no_volume_weight | no_count_weight | no_unit_weight

    Only "ok" lines count towards a recipe total. A "weak_match" line carries the weight and
    nutrients it would add, so a reviewer can see what accepting the proposed link changes."""
    grams: float | None = None
    method: str = ""
    basis: str = ""
    nutrients: dict[str, float] = field(default_factory=dict)


def _parsed(portions: tuple[Portion, ...]) -> list[ParsedPortion]:
    return [p for p in (parse_portion(portion) for portion in portions) if p]


def _grams_per_ml(portions: list[ParsedPortion], context: frozenset[str]) -> ParsedPortion | None:
    volume = [p for p in portions if p.kind == "volume"]
    if not volume:
        return None
    # Prefer the portion whose preparation ("chopped", "packed") the recipe also mentions, then the
    # plainest one, then the largest measure: a cup is weighed more precisely than a teaspoon.
    return min(
        volume,
        key=lambda p: (-len(p.qualifier & context), len(p.qualifier - context), -ML_PER_UNIT[p.unit]),
    )


def _count_portion(
    portions: list[ParsedPortion], unit_tokens: frozenset[str], food_tokens: frozenset[str], context: frozenset[str]
) -> ParsedPortion | None:
    count = [p for p in portions if p.kind == "count"]
    if not count:
        return None

    if unit_tokens and not (unit_tokens & _GENERIC_COUNT_UNITS):
        # a real household unit ("clove", "stick", "can"): only a portion with that label will do
        named = [p for p in count if unit_tokens & p.label]
        return min(named, key=lambda p: len(p.qualifier)) if named else None

    for size in _SIZES:
        size_tokens = frozenset(size.split())
        if size_tokens <= context:
            sized = [p for p in count if size_tokens <= (p.label | p.qualifier)]
            if sized:
                return sized[0]

    named_after_food = [p for p in count if p.label <= food_tokens]
    if named_after_food:
        return named_after_food[0]
    for label in _COUNT_FALLBACK:
        for portion in count:
            if label in portion.label:
                return portion
    return None


def ingredient_nutrition(ingredient: IngredientInput, link: FoodLink | None) -> IngredientResult:
    if not ingredient.food_name:
        return IngredientResult("no_food")
    if link is None or link.record is None:
        return IngredientResult("no_link")
    if not ingredient.quantity or ingredient.quantity <= 0:
        return IngredientResult("no_quantity")

    quantity = ingredient.quantity
    unit = ingredient.unit
    portions = _parsed(link.portions)
    food_tokens = frozenset(tokens(ingredient.food_name))
    context = frozenset(tokens(f"{ingredient.food_name} {ingredient.context}"))
    unit_tokens = frozenset(tokens(unit.name)) if unit else frozenset()

    grams: float | None = None
    method = basis = ""
    standard = unit.standard_unit if unit else None
    scale = (unit.standard_quantity or 1.0) if unit else 1.0

    if standard in _STANDARD_GRAMS:
        grams, method, basis = quantity * scale * _STANDARD_GRAMS[standard], "weight", standard
    elif standard in _STANDARD_ML or unit_tokens & _TINY_ML.keys():
        if standard in _STANDARD_ML:
            milliliters = quantity * scale * _STANDARD_ML[standard]
        else:
            milliliters = quantity * _TINY_ML[next(iter(unit_tokens & _TINY_ML.keys()))]
        density = _grams_per_ml(portions, context)
        if density is None:
            return IngredientResult("no_volume_weight")
        grams, method = milliliters * density.grams_per_ml, "volume"
        basis = f"{density.source.amount:g} {density.source.text} = {density.source.grams:g} g"
    else:
        portion = _count_portion(portions, unit_tokens, food_tokens, context)
        if portion is None:
            return IngredientResult("no_unit_weight" if unit_tokens - _GENERIC_COUNT_UNITS else "no_count_weight")
        grams, method = quantity * portion.grams_per_unit, "count"
        basis = f"{portion.source.amount:g} {portion.source.text} = {portion.source.grams:g} g"

    nutrients = {key: value * grams / 100 for key, value in link.record.nutrients.items()}
    return IngredientResult("weak_match" if link.method == "search_weak" else "ok", grams, method, basis, nutrients)


@dataclass(slots=True)
class RecipeNutrition:
    total: dict[str, float]
    per_serving: dict[str, float] | None
    results: list[IngredientResult]

    @property
    def counted(self) -> int:
        return sum(1 for r in self.results if r.status == "ok")

    @property
    def countable(self) -> int:
        """Lines that name a food with a quantity; "salt, to taste" is not expected to count."""
        return sum(1 for r in self.results if r.status not in ("no_food", "no_quantity"))


def recipe_nutrition(
    ingredients: list[tuple[IngredientInput, FoodLink | None]], servings: float | None
) -> RecipeNutrition:
    results = [ingredient_nutrition(ingredient, link) for ingredient, link in ingredients]
    total = dict.fromkeys(NUTRIENT_KEYS, 0.0)
    for result in results:
        if result.status != "ok":
            continue
        for key, value in result.nutrients.items():
            total[key] += value
    per_serving = {key: value / servings for key, value in total.items()} if servings and servings > 0 else None
    return RecipeNutrition(total, per_serving, results)
