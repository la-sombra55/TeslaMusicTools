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
