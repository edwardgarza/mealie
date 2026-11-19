from dataclasses import dataclass


@dataclass(frozen=True)
class NutrientDef:
    key: str
    """Mealie's own identifier, independent of any one food database"""
    unit: str
    fdc_ids: tuple[int, ...]
    """USDA FoodData Central nutrient ids, most preferred first"""


NUTRIENTS: tuple[NutrientDef, ...] = (
    # 1008 is the published energy value; Foundation Foods often carry only the Atwater figures
    NutrientDef("energy_kcal", "kcal", (1008, 2047, 2048)),
    NutrientDef("protein_g", "g", (1003,)),
    NutrientDef("fat_g", "g", (1004,)),
    NutrientDef("carbohydrate_g", "g", (1005,)),
    NutrientDef("fiber_g", "g", (1079,)),
    NutrientDef("sugar_g", "g", (2000, 1063)),
    NutrientDef("saturated_fat_g", "g", (1258,)),
    NutrientDef("monounsaturated_fat_g", "g", (1292,)),
    NutrientDef("polyunsaturated_fat_g", "g", (1293,)),
    NutrientDef("trans_fat_g", "g", (1257,)),
    NutrientDef("cholesterol_mg", "mg", (1253,)),
    NutrientDef("sodium_mg", "mg", (1093,)),
    NutrientDef("potassium_mg", "mg", (1092,)),
    NutrientDef("calcium_mg", "mg", (1087,)),
    NutrientDef("iron_mg", "mg", (1089,)),
    NutrientDef("magnesium_mg", "mg", (1090,)),
    NutrientDef("phosphorus_mg", "mg", (1091,)),
    NutrientDef("zinc_mg", "mg", (1095,)),
    NutrientDef("vitamin_a_ug", "µg", (1106,)),
    NutrientDef("vitamin_c_mg", "mg", (1162,)),
    NutrientDef("vitamin_d_ug", "µg", (1114,)),
    NutrientDef("vitamin_e_mg", "mg", (1109,)),
    NutrientDef("vitamin_k_ug", "µg", (1185,)),
    NutrientDef("thiamin_mg", "mg", (1165,)),
    NutrientDef("riboflavin_mg", "mg", (1166,)),
    NutrientDef("niacin_mg", "mg", (1167,)),
    NutrientDef("vitamin_b6_mg", "mg", (1175,)),
    NutrientDef("folate_ug", "µg", (1177,)),
    NutrientDef("vitamin_b12_ug", "µg", (1178,)),
)

NUTRIENT_KEYS: tuple[str, ...] = tuple(n.key for n in NUTRIENTS)
