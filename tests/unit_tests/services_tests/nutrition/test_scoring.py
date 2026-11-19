import pytest

from mealie.services.nutrition.scoring import ENCOURAGE, LIMIT, nrf_9_3


def test_nrf_is_undefined_without_energy():
    assert nrf_9_3({"protein_g": 10}) is None
    assert nrf_9_3({"energy_kcal": 0, "protein_g": 10}) is None


def test_nrf_adds_encouraged_and_subtracts_limited_per_100_kcal():
    # 200 kcal carrying half the protein daily value and half the sodium limit
    score = nrf_9_3({"energy_kcal": 200, "protein_g": 25, "sodium_mg": 1150})

    assert score is not None
    by_key = {c.key: c for c in score.components}
    # per 100 kcal that is a quarter of each reference amount
    assert by_key["protein_g"].amount == pytest.approx(12.5)
    assert by_key["protein_g"].percent == pytest.approx(25)
    assert by_key["sodium_mg"].percent == pytest.approx(25)
    assert score.encourage == pytest.approx(25)
    assert score.limit == pytest.approx(25)
    assert score.score == pytest.approx(0)


def test_nrf_caps_encouraged_nutrients_but_not_limited_ones():
    # 100 kcal with three times the vitamin C daily value and three times the sodium limit
    score = nrf_9_3({"energy_kcal": 100, "vitamin_c_mg": 270, "sodium_mg": 6900})

    assert score is not None
    by_key = {c.key: c for c in score.components}
    assert by_key["vitamin_c_mg"].percent == pytest.approx(100)
    assert by_key["sodium_mg"].percent == pytest.approx(300)
    assert score.score == pytest.approx(-200)


def test_nrf_does_not_depend_on_portion_size():
    serving = {"energy_kcal": 150, "protein_g": 8, "fiber_g": 3, "calcium_mg": 120, "sugar_g": 9}
    whole_recipe = {key: value * 6 for key, value in serving.items()}

    assert nrf_9_3(serving).score == pytest.approx(nrf_9_3(whole_recipe).score)


def test_nrf_reports_every_component():
    score = nrf_9_3({"energy_kcal": 100})

    assert score is not None
    assert [c.key for c in score.components] == [*ENCOURAGE, *LIMIT]
    assert score.score == 0


# --- Nutri-Score -------------------------------------------------------------------------------

from mealie.services.nutrition.scoring import nutri_score  # noqa: E402


def _dish(energy_kj=0.0, sugars=0.0, saturated_fat=0.0, salt=0.0, protein=0.0, fiber=0.0) -> dict[str, float]:
    """Nutrient totals for exactly 100 g of food, from per-100 g label values"""
    return {
        "energy_kcal": energy_kj / 4.184,
        "sugar_g": sugars,
        "saturated_fat_g": saturated_fat,
        "sodium_mg": salt / 2.5 * 1000,
        "protein_g": protein,
        "fiber_g": fiber,
    }


def _points(score):
    return {c.key: c.points for c in score.components}


def test_nutri_score_is_undefined_without_weight():
    assert nutri_score({"energy_kcal": 100}, 0, 0) is None


def test_nutri_score_points_and_grade_for_a_mixed_dish():
    nutrients = _dish(energy_kj=1000, sugars=10.5, saturated_fat=2.5, salt=0.5, protein=8, fiber=3.5)

    score = nutri_score(nutrients, 100, 50)

    assert score is not None
    assert _points(score) == {
        "energy": 2,
        "sugars": 3,
        "saturated_fat": 2,
        "salt": 2,
        "protein": 3,
        "fiber": 1,
        "fruits_vegetables_legumes": 1,
    }
    assert (score.negative, score.positive, score.score, score.grade) == (9, 5, 4, "C")


def test_nutri_score_scales_totals_to_100_g():
    per_100_g = _dish(energy_kj=1000, sugars=10.5, saturated_fat=2.5, salt=0.5, protein=8, fiber=3.5)
    whole_dish = {key: value * 12.5 for key, value in per_100_g.items()}

    assert nutri_score(whole_dish, 1250, 625).score == nutri_score(per_100_g, 100, 50).score


def test_nutri_score_ignores_protein_once_negative_points_reach_eleven():
    # energy 5 + saturated fat 6 = 11 negative points
    nutrients = _dish(energy_kj=1700, saturated_fat=6.5, protein=20, fiber=8)

    score = nutri_score(nutrients, 100, 0)

    assert score is not None
    protein = next(c for c in score.components if c.key == "protein")
    assert (protein.points, protein.counted) == (7, False)
    assert (score.negative, score.positive, score.score, score.grade) == (11, 5, 6, "C")


def test_nutri_score_thresholds_are_exclusive():
    # a value exactly on a threshold does not earn the point
    assert _points(nutri_score(_dish(sugars=3.4), 100, 0))["sugars"] == 0
    assert _points(nutri_score(_dish(sugars=3.5), 100, 0))["sugars"] == 1
    assert _points(nutri_score({}, 100, 80))["fruits_vegetables_legumes"] == 2
    assert _points(nutri_score({}, 100, 81))["fruits_vegetables_legumes"] == 5


@pytest.mark.parametrize(
    ("sugars", "expected_score", "expected_grade"),
    [(0, 0, "A"), (3.5, 1, "B"), (6.9, 2, "B"), (10.1, 3, "C"), (34.1, 10, "C"), (37.1, 11, "D")],
)
def test_nutri_score_grade_boundaries(sugars, expected_score, expected_grade):
    score = nutri_score(_dish(sugars=sugars), 100, 0)

    assert (score.score, score.grade) == (expected_score, expected_grade)


def test_nutri_score_worst_grade():
    score = nutri_score(_dish(energy_kj=3400, sugars=52, saturated_fat=11, salt=4.1), 100, 0)

    assert (score.negative, score.grade) == (55, "E")
