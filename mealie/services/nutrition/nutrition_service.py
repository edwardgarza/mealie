from functools import lru_cache

from mealie.schema.recipe.recipe import RecipeOut
from mealie.schema.recipe.recipe_ingredient import RecipeIngredient
from mealie.schema.recipe.recipe_nutrition import Nutrition
from mealie.schema.recipe.recipe_nutrition_calculated import (
    CalculatedFoodMatch,
    CalculatedIngredientOut,
    CalculatedNrfComponent,
    CalculatedNrfOut,
    CalculatedNutrientInfo,
    CalculatedNutriScoreComponent,
    CalculatedNutriScoreOut,
    CalculatedNutritionOut,
    NutritionRecordSummary,
)

from .calculator import IngredientInput, UnitInfo, recipe_nutrition
from .dataset import FoodRecord
from .food_groups import is_fruit_vegetable_or_legume
from .matching import FoodLink, FoodMatcher
from .nutrients import NUTRIENTS
from .portions import parse_portion
from .scoring import nrf_9_3, nutri_score

# Fields of the recipe's saved Nutrition -> the calculator's nutrient keys
_STORED_FIELDS: dict[str, str] = {
    "calories": "energy_kcal",
    "protein_content": "protein_g",
    "fat_content": "fat_g",
    "carbohydrate_content": "carbohydrate_g",
    "fiber_content": "fiber_g",
    "sugar_content": "sugar_g",
    "saturated_fat_content": "saturated_fat_g",
    "trans_fat_content": "trans_fat_g",
    "cholesterol_content": "cholesterol_mg",
    "sodium_content": "sodium_mg",
}


@lru_cache(maxsize=1)
def _matcher() -> FoodMatcher:
    return FoodMatcher()


@lru_cache(maxsize=4096)
def _link(name: str, other_names: tuple[str, ...]) -> FoodLink:
    return _matcher().link(name, other_names)


def _match(record: FoodRecord) -> CalculatedFoodMatch:
    return CalculatedFoodMatch(id=str(record.id), name=record.name, source=record.source)


def _stored(nutrition: Nutrition | None) -> dict[str, float]:
    stored: dict[str, float] = {}
    if nutrition is None:
        return stored
    for field, key in _STORED_FIELDS.items():
        try:
            stored[key] = float(getattr(nutrition, field))
        except TypeError, ValueError:
            continue
    return stored


NUTRITION_SOURCE_USDA = "usda"


def _food_link(ingredient: RecipeIngredient) -> FoodLink | None:
    food = ingredient.food
    if food is None or not food.name:
        return None
    other_names = [getattr(food, "plural_name", None), *(alias.name for alias in getattr(food, "aliases", None) or [])]
    names = tuple(name for name in other_names if name)

    chosen = getattr(food, "nutrition_source_id", None)
    if chosen and getattr(food, "nutrition_source", None) == NUTRITION_SOURCE_USDA:
        manual = _matcher().manual(chosen, food.name, names)
        if manual:
            return manual
    return _link(food.name, names)


def record_summary(record: FoodRecord) -> NutritionRecordSummary:
    kinds = {parsed.kind for parsed in (parse_portion(portion) for portion in record.portions) if parsed}
    return NutritionRecordSummary(
        id=str(record.id),
        name=record.name,
        source=record.source,
        category=record.category,
        energy_kcal=record.nutrients.get("energy_kcal"),
        protein_g=record.nutrients.get("protein_g"),
        fat_g=record.nutrients.get("fat_g"),
        carbohydrate_g=record.nutrients.get("carbohydrate_g"),
        has_volume_weight="volume" in kinds,
        has_count_weight="count" in kinds,
    )


def search_nutrition_records(text: str, limit: int = 20) -> list[NutritionRecordSummary]:
    return [record_summary(hit.record) for hit in _matcher().search_text(text, limit)]


def nutrition_record_exists(record_id: str) -> bool:
    return record_id.isdigit() and _matcher().dataset.get(int(record_id)) is not None


def calculate_recipe_nutrition(recipe: RecipeOut) -> CalculatedNutritionOut:
    """Estimate a recipe's nutrition from its parsed ingredients, with one row per ingredient."""
    lines = [i for i in recipe.recipe_ingredient if not i.referenced_recipe and (i.food or i.note or i.quantity)]

    inputs: list[tuple[IngredientInput, FoodLink | None]] = []
    for ingredient in lines:
        unit = ingredient.unit
        unit_info = (
            UnitInfo(unit.name, getattr(unit, "standard_quantity", None), getattr(unit, "standard_unit", None))
            if unit and unit.name
            else None
        )
        context = " ".join(text for text in (ingredient.note, ingredient.original_text) if text)
        food_name = ingredient.food.name if ingredient.food else None
        inputs.append((IngredientInput(ingredient.quantity, unit_info, food_name, context), _food_link(ingredient)))

    result = recipe_nutrition(inputs, recipe.recipe_servings)

    rows = []
    for ingredient, (_, link), line in zip(lines, inputs, result.results, strict=True):
        rows.append(
            CalculatedIngredientOut(
                reference_id=ingredient.reference_id,
                display=ingredient.display,
                food_id=getattr(ingredient.food, "id", None) if ingredient.food else None,
                food_name=ingredient.food.name if ingredient.food else None,
                status=line.status,
                counted=line.status == "ok",
                grams=round(line.grams, 1) if line.grams is not None else None,
                method=line.method,
                basis=line.basis,
                match=_match(link.record) if link and link.record else None,
                match_method=link.method if link else "",
                match_assumed=link.assumed_default if link else False,
                alternatives=[
                    _match(hit.record)
                    for hit in (link.suggestions if link else [])
                    if not (link and link.record and hit.record.id == link.record.id)
                ][:4],
                nutrients={key: round(value, 2) for key, value in line.nutrients.items()},
            )
        )

    nrf = None
    score = nrf_9_3(result.total)
    if score:
        counted = [line for line in result.results if line.status == "ok"]
        nrf = CalculatedNrfOut(
            score=round(score.score, 1),
            encourage=round(score.encourage, 1),
            limit=round(score.limit, 1),
            components=[
                CalculatedNrfComponent(
                    key=c.key,
                    kind=c.kind,
                    amount=round(c.amount, 2),
                    reference=c.reference,
                    percent=round(c.percent, 1),
                    missing_lines=sum(1 for line in counted if c.key not in line.nutrients),
                )
                for c in score.components
            ],
        )

    # The Nutri-Score works per 100 g. Only raw ingredient weights are known, so water lost or
    # absorbed in cooking is not reflected.
    weight = produce = 0.0
    for (_, link), line in zip(inputs, result.results, strict=True):
        if line.status == "ok" and line.grams:
            weight += line.grams
            if link and link.record and is_fruit_vegetable_or_legume(link.record):
                produce += line.grams
    grade = nutri_score(result.total, weight, produce)
    nutri = None
    if grade:
        nutri = CalculatedNutriScoreOut(
            score=grade.score,
            grade=grade.grade,
            negative=grade.negative,
            positive=grade.positive,
            weight=round(weight, 1),
            components=[
                CalculatedNutriScoreComponent(
                    key=c.key,
                    kind=c.kind,
                    value=round(c.value, 2),
                    unit=c.unit,
                    points=c.points,
                    max_points=c.max_points,
                    counted=c.counted,
                )
                for c in grade.components
            ],
        )

    return CalculatedNutritionOut(
        servings=recipe.recipe_servings or None,
        counted_lines=result.counted,
        countable_lines=result.countable,
        nutrients=[CalculatedNutrientInfo(key=n.key, unit=n.unit) for n in NUTRIENTS],
        total={key: round(value, 2) for key, value in result.total.items()},
        per_serving=(
            {key: round(value, 2) for key, value in result.per_serving.items()} if result.per_serving else None
        ),
        stored_per_serving=_stored(recipe.nutrition),
        nrf=nrf,
        nutri_score=nutri,
        ingredients=rows,
    )
