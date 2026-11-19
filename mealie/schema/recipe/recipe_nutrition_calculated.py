from uuid import UUID

from mealie.schema._mealie import MealieModel
from mealie.schema._mealie.mealie_model import MealieOutModel


class CalculatedNutrientInfo(MealieOutModel):
    key: str
    unit: str


class CalculatedFoodMatch(MealieOutModel):
    id: str
    name: str
    source: str


class NutritionRecordSummary(MealieOutModel):
    """One entry of the bundled food database, as offered when choosing a food's nutrition source"""

    id: str
    name: str
    source: str
    category: str = ""
    energy_kcal: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    carbohydrate_g: float | None = None
    """Per 100 g"""
    has_volume_weight: bool = False
    """Has a cup or spoon weight, so volume measures can be converted"""
    has_count_weight: bool = False
    """Has a per-item weight, so "2 onions" can be converted"""


class FoodNutritionLinkUpdate(MealieModel):
    record_id: str | None = None
    """Id of the database entry to use for this food; null goes back to automatic matching"""


class CalculatedIngredientOut(MealieOutModel):
    reference_id: UUID | None = None
    display: str = ""
    food_id: UUID | None = None
    food_name: str | None = None

    status: str
    """ok | weak_match | no_food | no_link | no_quantity | no_volume_weight | no_count_weight | no_unit_weight"""
    counted: bool = False
    """Whether this line is part of the totals"""

    grams: float | None = None
    method: str = ""
    """How the weight was derived: weight | volume | count"""
    basis: str = ""
    """The household measure the weight came from, e.g. "1 cup, chopped = 160 g\""""

    match: CalculatedFoodMatch | None = None
    match_method: str = ""
    """manual | curated | curated_macros | search | search_weak | none"""
    match_assumed: bool = False
    """The food named no variety ("milk"), so a default was assumed"""
    alternatives: list[CalculatedFoodMatch] = []

    nutrients: dict[str, float] = {}


class CalculatedNrfComponent(MealieOutModel):
    key: str
    kind: str
    """encourage | limit"""
    amount: float
    """Amount per 100 kcal"""
    reference: float
    """Daily value (encourage) or daily limit (limit)"""
    percent: float
    """Share of the reference amount per 100 kcal; capped at 100 for nutrients to encourage"""
    missing_lines: int = 0
    """Counted ingredient lines whose food has no value for this nutrient; they add nothing to it"""


class CalculatedNrfOut(MealieOutModel):
    score: float
    """Nutrient Rich Foods index 9.3 per 100 kcal: encourage minus limit"""
    encourage: float
    limit: float
    components: list[CalculatedNrfComponent] = []


class CalculatedNutriScoreComponent(MealieOutModel):
    key: str
    kind: str
    """negative | positive"""
    value: float
    """Per 100 g, in `unit`"""
    unit: str
    points: int
    max_points: int
    counted: bool = True
    """Protein is left out of the score when the negative points are high"""


class CalculatedNutriScoreOut(MealieOutModel):
    score: int
    """Negative points minus positive points; lower is better"""
    grade: str
    """A to E"""
    negative: int
    positive: int
    weight: float
    """Grams of counted ingredients the per-100 g values are based on (raw weights)"""
    components: list[CalculatedNutriScoreComponent] = []


class CalculatedNutritionOut(MealieOutModel):
    servings: float | None = None
    counted_lines: int = 0
    countable_lines: int = 0
    """Lines that name a food and a quantity; the ones a complete calculation would count"""

    nutrients: list[CalculatedNutrientInfo] = []
    total: dict[str, float] = {}
    per_serving: dict[str, float] | None = None
    stored_per_serving: dict[str, float] = {}
    """The nutrition already saved on the recipe (scraped or entered by hand), under the same keys"""

    nrf: CalculatedNrfOut | None = None
    """None when no calories were counted"""
    nutri_score: CalculatedNutriScoreOut | None = None
    """None when no ingredient weight was counted"""

    ingredients: list[CalculatedIngredientOut] = []
