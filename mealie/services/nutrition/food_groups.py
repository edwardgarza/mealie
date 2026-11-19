from .dataset import FoodRecord

# USDA food categories whose foods count towards the fruit, vegetable and legume share
_FRUIT = "Fruits and Fruit Juices"
_VEGETABLE = "Vegetables and Vegetable Products"
_LEGUME = "Legumes and Legume Products"
_HERB = "Spices and Herbs"

# Starchy tubers are not counted as vegetables by the Nutri-Score
_STARCHY = {"potato", "yam", "cassava", "taro", "arrowroot", "yautia"}
# Forms that no longer count as the whole food
_NOT_WHOLE = {"juice", "nectar", "syrup", "sauce", "powder", "flour", "oil", "chip", "candied", "pickle"}
# In this category but not pulses: peanuts are scored as nuts, and soy products are processed
_NOT_PULSE = {"peanut", "sauce", "milk", "flour", "oil", "tofu", "tempeh", "miso", "protein", "bacon", "burger"}
_FRESH = {"fresh", "raw"}


def is_fruit_vegetable_or_legume(record: FoodRecord) -> bool:
    """Whether a food counts towards the Nutri-Score's fruit, vegetable and legume share.

    A rule of thumb over the USDA food category and name; the official definition is a list of
    food groups that the dataset does not carry.
    """
    words = record.all_tokens
    if record.category == _VEGETABLE:
        return not (words & _STARCHY) and not (words & _NOT_WHOLE)
    if record.category == _FRUIT:
        return not (words & _NOT_WHOLE)
    if record.category == _LEGUME:
        return not (words & _NOT_PULSE)
    if record.category == _HERB:
        return bool(words & _FRESH)
    return False
