"""Nutrient Rich Foods index (NRF 9.3), a nutrient-density score.

Method: Drewnowski A. "The Nutrient Rich Foods Index helps to identify healthy, affordable foods",
Am J Clin Nutr 2010;91(suppl):1095S-1101S. Per 100 kcal, the score adds the percentage of the daily
value supplied for nine nutrients to encourage, each capped at 100%, and subtracts the percentage
of the daily limit for three nutrients to limit.

Two departures from the published index, both forced by the data:
- reference amounts are the current FDA Daily Values (21 CFR 101.9), because the nutrient data is in
  their units (vitamin A as µg RAE, vitamin E as mg alpha-tocopherol) rather than the older IU;
- the sugar term uses total sugars. The USDA SR Legacy and Foundation files do not separate added
  sugars.
"""

from dataclasses import dataclass

# nutrient key -> daily value
ENCOURAGE: dict[str, float] = {
    "protein_g": 50,
    "fiber_g": 28,
    "vitamin_a_ug": 900,
    "vitamin_c_mg": 90,
    "vitamin_e_mg": 15,
    "calcium_mg": 1300,
    "iron_mg": 18,
    "magnesium_mg": 420,
    "potassium_mg": 4700,
}
# nutrient key -> daily limit
LIMIT: dict[str, float] = {
    "saturated_fat_g": 20,
    "sugar_g": 50,
    "sodium_mg": 2300,
}


@dataclass(frozen=True, slots=True)
class NrfComponent:
    key: str
    kind: str
    """encourage | limit"""
    amount: float
    """Amount of the nutrient per 100 kcal"""
    reference: float
    percent: float
    """Share of the reference amount per 100 kcal; capped at 100 for nutrients to encourage"""


@dataclass(frozen=True, slots=True)
class NrfScore:
    score: float
    encourage: float
    limit: float
    components: tuple[NrfComponent, ...]


def nrf_9_3(nutrients: dict[str, float]) -> NrfScore | None:
    """Score any amount of food (an ingredient, a serving, a whole recipe) from its nutrient totals.

    Returns None when the food has no energy, since the index is defined per 100 kcal.
    """
    energy = nutrients.get("energy_kcal", 0)
    if energy <= 0:
        return None

    per_100_kcal = 100 / energy
    components: list[NrfComponent] = []
    for key, reference in ENCOURAGE.items():
        amount = nutrients.get(key, 0) * per_100_kcal
        components.append(NrfComponent(key, "encourage", amount, reference, min(100 * amount / reference, 100)))
    for key, reference in LIMIT.items():
        amount = nutrients.get(key, 0) * per_100_kcal
        components.append(NrfComponent(key, "limit", amount, reference, 100 * amount / reference))

    encourage = sum(c.percent for c in components if c.kind == "encourage")
    limit = sum(c.percent for c in components if c.kind == "limit")
    return NrfScore(encourage - limit, encourage, limit, tuple(components))


# ---------------------------------------------------------------------------------------------
# Nutri-Score, 2023 algorithm for general foods
#
# Method: Merz B. et al. "Nutri-Score 2023 update", Nat Food 2024;5:102-110, and the Scientific
# Committee of the Nutri-Score reports published by Santé publique France. Point tables checked
# against the Open Food Facts implementation of the same algorithm.
#
# Per 100 g, points are given for energy, sugars, saturated fat and salt (negative) and for
# protein, fibre and the share of fruit, vegetables and legumes (positive). A component earns one
# point for each threshold its value exceeds.
#
# Only the general-food rules are implemented. The separate rules for beverages, for fats, oils,
# nuts and seeds, for cheese and for red meat are not applied, so a drink or a dressing scored
# here is scored as a dish.
# ---------------------------------------------------------------------------------------------

KJ_PER_KCAL = 4.184
SALT_PER_SODIUM = 2.5

_NS_ENERGY_KJ = (335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350)
_NS_SUGARS_G = (3.4, 6.8, 10, 14, 17, 20, 24, 27, 31, 34, 37, 41, 44, 48, 51)
_NS_SATURATED_FAT_G = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
_NS_SALT_G = (0.2, 0.4, 0.6, 0.8, 1, 1.2, 1.4, 1.6, 1.8, 2, 2.2, 2.4, 2.6, 2.8, 3, 3.2, 3.4, 3.6, 3.8, 4)
_NS_PROTEIN_G = (2.4, 4.8, 7.2, 9.6, 12, 14, 17)
_NS_FIBER_G = (3.0, 4.1, 5.2, 6.3, 7.4)
# above 40% -> 1 point, above 60% -> 2, above 80% -> 5
_NS_FRUIT_VEGETABLE_LEGUME_PERCENT = (40, 60, 80, 80, 80)

# Protein only counts while the negative points stay below this
_NS_PROTEIN_CUTOFF = 11
# highest score for each grade; anything above the last is E
_NS_GRADES = ((0, "A"), (2, "B"), (10, "C"), (18, "D"))


@dataclass(frozen=True, slots=True)
class NutriScoreComponent:
    key: str
    kind: str
    """negative | positive"""
    value: float
    """Per 100 g, in the unit the thresholds use (kJ, g or %)"""
    unit: str
    points: int
    max_points: int
    counted: bool = True


@dataclass(frozen=True, slots=True)
class NutriScore:
    score: int
    grade: str
    negative: int
    positive: int
    components: tuple[NutriScoreComponent, ...]


def _points(value: float, thresholds: tuple[float, ...]) -> int:
    return sum(1 for threshold in thresholds if value > threshold)


def nutri_score(nutrients: dict[str, float], weight_g: float, fruit_vegetable_legume_g: float) -> NutriScore | None:
    """Score a dish from its nutrient totals, its total weight and the weight of its fruit,
    vegetables and legumes. Returns None when there is no weight to scale by."""
    if weight_g <= 0:
        return None

    per_100_g = 100 / weight_g

    def amount(key: str) -> float:
        return nutrients.get(key, 0) * per_100_g

    negative = [
        ("energy", amount("energy_kcal") * KJ_PER_KCAL, "kJ", _NS_ENERGY_KJ),
        ("sugars", amount("sugar_g"), "g", _NS_SUGARS_G),
        ("saturated_fat", amount("saturated_fat_g"), "g", _NS_SATURATED_FAT_G),
        ("salt", amount("sodium_mg") / 1000 * SALT_PER_SODIUM, "g", _NS_SALT_G),
    ]
    positive = [
        ("protein", amount("protein_g"), "g", _NS_PROTEIN_G),
        ("fiber", amount("fiber_g"), "g", _NS_FIBER_G),
        (
            "fruits_vegetables_legumes",
            min(100 * fruit_vegetable_legume_g / weight_g, 100),
            "%",
            _NS_FRUIT_VEGETABLE_LEGUME_PERCENT,
        ),
    ]

    components = [
        NutriScoreComponent(key, "negative", value, unit, _points(value, thresholds), len(thresholds))
        for key, value, unit, thresholds in negative
    ]
    negative_points = sum(c.points for c in components)
    protein_counts = negative_points < _NS_PROTEIN_CUTOFF
    components += [
        NutriScoreComponent(
            key,
            "positive",
            value,
            unit,
            _points(value, thresholds),
            len(thresholds),
            key != "protein" or protein_counts,
        )
        for key, value, unit, thresholds in positive
    ]
    positive_points = sum(c.points for c in components if c.kind == "positive" and c.counted)

    score = negative_points - positive_points
    grade = next((letter for limit, letter in _NS_GRADES if score <= limit), "E")
    return NutriScore(score, grade, negative_points, positive_points, tuple(components))
