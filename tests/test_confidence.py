from tesla_music.confidence import calculate_confidence


def test_exact_match_scores_100():
    result = calculate_confidence("Chris Brown", "Chris Brown")

    assert result["score"] == 100


def test_case_only_difference_scores_95():
    result = calculate_confidence("Chris Brown", "chris brown")

    assert result["score"] == 95
    assert result["reason"] == "Capitalization difference only"


def test_word_order_difference_scores_85():
    result = calculate_confidence("Kanye West", "West Kanye")

    assert result["score"] == 85
    assert result["reason"] == "Word order difference"


def test_unrelated_names_score_0():
    result = calculate_confidence("Chris Brown", "50 Cent")

    assert result["score"] == 0
    assert result["reason"] == "No match"


def test_accent_only_difference_scores_95():
    result = calculate_confidence("Beyonce", "Beyoncé")

    assert result["score"] == 95
    assert result["reason"] == "Accent difference only"


def test_accent_and_case_difference_together_still_scores_95():
    result = calculate_confidence("BEYONCE", "beyoncé")

    assert result["score"] == 95


def test_accent_difference_does_not_mask_a_real_word_order_difference():
    result = calculate_confidence("Beyoncé West", "west beyonce")

    assert result["score"] == 85
    assert result["reason"] == "Word order difference"


def test_period_difference_scores_90():
    result = calculate_confidence("R Kelly", "R. Kelly")

    assert result["score"] == 90
    assert result["reason"] == "Punctuation or spacing difference only"


def test_apostrophe_difference_scores_90():
    result = calculate_confidence("Lil Wayne", "Lil' Wayne")

    assert result["score"] == 90


def test_all_periods_collapsing_a_name_scores_90():
    result = calculate_confidence("T.I.", "TI")

    assert result["score"] == 90


def test_compound_word_spacing_difference_scores_90():
    result = calculate_confidence("Outkast", "Out Kast")

    assert result["score"] == 90
    assert result["reason"] == "Punctuation or spacing difference only"


def test_three_word_compound_spacing_difference_scores_90():
    result = calculate_confidence("Sugarhill Gang", "Sugar Hill Gang")

    assert result["score"] == 90


def test_likely_spelling_variation_scores_65():
    result = calculate_confidence("Missy Elliot", "Missy Elliott")

    assert result["score"] == 65
    assert result["reason"] == "Possible spelling variation — please review"


def test_short_names_are_not_fuzzy_matched_even_when_similar():
    # "Nas" and "Nash" are 86% similar by raw character overlap but are
    # different real artists -- short names must require an exact match.
    result = calculate_confidence("Nas", "Nash")

    assert result["score"] == 0
    assert result["reason"] == "No match"


def test_names_with_digits_are_not_fuzzy_matched():
    # A digit difference is a different identifier, not a typo -- e.g. two
    # sequentially-numbered/templated names shouldn't be treated as
    # spelling variants of each other just because they're mostly the same.
    result = calculate_confidence("Artist 0001", "Artist 0002")

    assert result["score"] == 0
    assert result["reason"] == "No match"


def test_dissimilar_names_still_score_0():
    result = calculate_confidence("Chris Brown", "50 Cent")

    assert result["score"] == 0
    assert result["reason"] == "No match"
