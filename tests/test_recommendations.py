from tesla_music.recommendations import build_recommendations


def test_keeps_the_artist_with_the_highest_count(make_song):
    duplicate_groups = [
        {
            "artists": [
                {"artist": "Chris Brown", "count": 97},
                {"artist": "chris brown", "count": 2},
            ],
            "score": 95,
            "reason": "Capitalization difference only",
        }
    ]
    artist_songs = {
        "chris brown": [make_song("a.mp3"), make_song("b.mp3")],
    }

    recommendations = build_recommendations(duplicate_groups, artist_songs)

    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation["keep"] == "Chris Brown"
    assert recommendation["keep_count"] == 97
    assert recommendation["confidence"] == 95
    assert recommendation["reason"] == "Capitalization difference only"
    assert len(recommendation["change"]) == 1
    assert recommendation["change"][0]["artist"] == "chris brown"
    assert len(recommendation["change"][0]["songs"]) == 2


def test_handles_missing_artist_songs_gracefully():
    duplicate_groups = [
        {
            "artists": [
                {"artist": "Chris Brown", "count": 97},
                {"artist": "chris brown", "count": 2},
            ],
            "score": 95,
            "reason": "Capitalization difference only",
        }
    ]

    recommendations = build_recommendations(duplicate_groups, artist_songs={})

    assert recommendations[0]["change"][0]["songs"] == []


def test_returns_empty_list_when_no_duplicate_groups():
    assert build_recommendations([], artist_songs={}) == []


def test_supports_groups_with_more_than_two_variants(make_song):
    duplicate_groups = [
        {
            "artists": [
                {"artist": "Jay-Z & Kanye West", "count": 60},
                {"artist": "JAY Z & Kanye West", "count": 1},
                {"artist": "jay-z & kanye west", "count": 3},
            ],
            "score": 85,
            "reason": "Word order difference",
        }
    ]
    artist_songs = {
        "JAY Z & Kanye West": [make_song("c.m4a")],
        "jay-z & kanye west": [make_song("d.m4a"), make_song("e.m4a"), make_song("f.m4a")],
    }

    recommendations = build_recommendations(duplicate_groups, artist_songs)

    recommendation = recommendations[0]
    assert recommendation["keep"] == "Jay-Z & Kanye West"
    assert [c["artist"] for c in recommendation["change"]] == [
        "jay-z & kanye west",
        "JAY Z & Kanye West",
    ]
