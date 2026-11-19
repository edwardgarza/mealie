from mealie.services.nutrition.matching import FoodMatcher

matcher = FoodMatcher()


def test_search_text_matches_a_word_that_is_still_being_typed():
    names = [hit.record.name for hit in matcher.search_text("quinoa cook")]

    assert names[0] == "Quinoa, cooked"


def test_search_text_does_not_depend_on_word_order():
    by_food_first = [hit.record.id for hit in matcher.search_text("potatoes flesh skin raw", limit=3)]
    by_food_last = [hit.record.id for hit in matcher.search_text("raw flesh skin potatoes", limit=3)]

    assert by_food_first == by_food_last
    assert matcher.dataset.get(by_food_first[0]).name == "Potatoes, flesh and skin, raw"


def test_search_text_returns_nothing_for_unknown_words():
    assert matcher.search_text("zwiebel") == []
    assert matcher.search_text("") == []


def test_manual_link_uses_the_chosen_record_and_is_not_flagged_for_review():
    chosen = matcher.search_text("potatoes flesh skin raw", limit=1)[0].record

    link = matcher.manual(str(chosen.id), "baby potatoes")

    assert link is not None
    assert link.record is chosen
    assert link.method == "manual"
    assert not link.needs_review


def test_manual_link_to_an_unknown_record_is_rejected():
    assert matcher.manual("999999999", "baby potatoes") is None
    assert matcher.manual("not-a-number", "baby potatoes") is None
