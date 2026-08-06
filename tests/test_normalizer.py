from collections import Counter

from tesla_music.normalizer import find_similar_artists


def test_find_similar_artists_groups_case_variants():
    artists = Counter({"Chris Brown": 97, "chris brown": 2})

    groups = find_similar_artists(artists)

    assert len(groups) == 1
    group = groups[0]
    assert {a["artist"] for a in group["artists"]} == {"Chris Brown", "chris brown"}
    assert group["score"] == 95
    assert group["reason"] == "Capitalization difference only"


def test_find_similar_artists_groups_hyphen_variants():
    artists = Counter({"Jay-Z & Kanye West": 60, "JAY Z & Kanye West": 1})

    groups = find_similar_artists(artists)

    assert len(groups) == 1
    group = groups[0]
    assert {a["artist"] for a in group["artists"]} == {
        "Jay-Z & Kanye West",
        "JAY Z & Kanye West",
    }
    assert group["score"] > 0


def test_find_similar_artists_does_not_group_distinct_artists():
    artists = Counter({"Chris Brown": 97, "Chris Brown & Tyga": 18, "50 Cent": 1})

    groups = find_similar_artists(artists)

    assert groups == []


def test_find_similar_artists_returns_empty_for_empty_input():
    assert find_similar_artists(Counter()) == []
