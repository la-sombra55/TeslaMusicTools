from tesla_music.recommendations import (
    build_album_recommendations,
    build_genre_recommendations,
    build_recommendations,
)


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


def test_build_genre_recommendations_keeps_the_genre_with_the_highest_count(make_song):
    genre_groups = [
        {
            "genres": [
                {"genre": "Hip-Hop", "count": 120},
                {"genre": "Hip Hop", "count": 15},
            ],
            "score": 85,
            "reason": "Word order difference",
        }
    ]
    artist_songs = {
        "Lupe Fiasco": [
            make_song("a.mp3", artist="Lupe Fiasco", genre="Hip Hop"),
            make_song("b.mp3", artist="Lupe Fiasco", genre="Hip Hop"),
        ],
        "Chris Brown": [make_song("c.mp3", artist="Chris Brown", genre="Hip-Hop")],
    }

    recommendations = build_genre_recommendations(genre_groups, artist_songs)

    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation["keep"] == "Hip-Hop"
    assert recommendation["keep_count"] == 120
    assert recommendation["confidence"] == 85
    assert len(recommendation["change"]) == 1
    assert recommendation["change"][0]["genre"] == "Hip Hop"
    assert len(recommendation["change"][0]["songs"]) == 2


def test_build_genre_recommendations_spans_songs_across_different_artists(make_song):
    # Genre grouping isn't scoped per artist -- a genre variant used by
    # different artists should all show up under one recommendation.
    genre_groups = [
        {
            "genres": [
                {"genre": "R&B", "count": 40},
                {"genre": "R & B", "count": 6},
            ],
            "score": 85,
            "reason": "Word order difference",
        }
    ]
    artist_songs = {
        "Beyoncé": [make_song("a.mp3", artist="Beyoncé", genre="R & B")],
        "Usher": [make_song("b.mp3", artist="Usher", genre="R & B")],
    }

    recommendations = build_genre_recommendations(genre_groups, artist_songs)

    assert len(recommendations[0]["change"][0]["songs"]) == 2


def test_build_genre_recommendations_candidates_include_songs(make_song):
    genre_groups = [
        {
            "genres": [
                {"genre": "Hip-Hop", "count": 2},
                {"genre": "Hip Hop", "count": 1},
            ],
            "score": 85,
            "reason": "Word order difference",
        }
    ]
    artist_songs = {
        "Lupe Fiasco": [
            make_song("a.mp3", artist="Lupe Fiasco", genre="Hip-Hop"),
            make_song("b.mp3", artist="Lupe Fiasco", genre="Hip-Hop"),
            make_song("c.mp3", artist="Lupe Fiasco", genre="Hip Hop"),
        ],
    }

    recommendations = build_genre_recommendations(genre_groups, artist_songs)

    candidates = recommendations[0]["candidates"]
    assert [c["genre"] for c in candidates] == ["Hip-Hop", "Hip Hop"]
    assert len(candidates[0]["songs"]) == 2
    assert len(candidates[1]["songs"]) == 1


def test_build_genre_recommendations_returns_empty_for_no_groups():
    assert build_genre_recommendations([], {}) == []


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


def test_candidates_includes_every_variant_sorted_by_count_with_songs(make_song):
    duplicate_groups = [
        {
            "artists": [
                {"artist": "Missy Elliot", "count": 12},
                {"artist": "Missy Elliott", "count": 8},
                {"artist": "MISSY ELLIOTT", "count": 3},
            ],
            "score": 65,
            "reason": "Possible spelling variation — please review",
        }
    ]
    artist_songs = {
        "Missy Elliot": [make_song("a.mp3")],
        "Missy Elliott": [make_song("b.mp3"), make_song("c.mp3")],
        "MISSY ELLIOTT": [],
    }

    recommendations = build_recommendations(duplicate_groups, artist_songs)

    candidates = recommendations[0]["candidates"]
    assert [c["artist"] for c in candidates] == ["Missy Elliot", "Missy Elliott", "MISSY ELLIOTT"]
    assert [c["count"] for c in candidates] == [12, 8, 3]
    assert len(candidates[0]["songs"]) == 1
    assert len(candidates[1]["songs"]) == 2


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


def test_build_album_recommendations_keeps_the_album_with_the_highest_count(make_song):
    album_groups_by_artist = {
        "T.I.": [
            {
                "albums": [
                    {"album": "The KING", "count": 15},
                    {"album": "The King", "count": 1},
                ],
                "score": 95,
                "reason": "Capitalization difference only",
            }
        ]
    }
    artist_songs = {
        "T.I.": [
            *[make_song(f"a{i}.mp3", artist="T.I.", album="The KING") for i in range(15)],
            make_song("b.mp3", artist="T.I.", album="The King"),
        ]
    }

    recommendations = build_album_recommendations(album_groups_by_artist, artist_songs)

    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation["artist"] == "T.I."
    assert recommendation["keep"] == "The KING"
    assert recommendation["keep_count"] == 15
    assert recommendation["confidence"] == 95
    assert len(recommendation["change"]) == 1
    assert recommendation["change"][0]["album"] == "The King"
    assert [s.path.name for s in recommendation["change"][0]["songs"]] == ["b.mp3"]


def test_build_album_recommendations_does_not_mix_up_different_artists(make_song):
    album_groups_by_artist = {
        "Artist A": [
            {
                "albums": [
                    {"album": "Greatest Hits", "count": 10},
                    {"album": "greatest hits", "count": 1},
                ],
                "score": 95,
                "reason": "Capitalization difference only",
            }
        ]
    }
    artist_songs = {
        "Artist A": [
            *[make_song(f"a{i}.mp3", artist="Artist A", album="Greatest Hits") for i in range(10)],
            make_song("b.mp3", artist="Artist A", album="greatest hits"),
        ],
        "Artist B": [make_song("c.mp3", artist="Artist B", album="greatest hits")],
    }

    recommendations = build_album_recommendations(album_groups_by_artist, artist_songs)

    assert len(recommendations) == 1
    assert recommendations[0]["change"][0]["songs"] == [
        artist_songs["Artist A"][-1]
    ]


def test_build_album_recommendations_candidates_includes_every_variant_with_songs(make_song):
    album_groups_by_artist = {
        "T.I.": [
            {
                "albums": [
                    {"album": "The KING", "count": 15},
                    {"album": "The King", "count": 1},
                ],
                "score": 95,
                "reason": "Capitalization difference only",
            }
        ]
    }
    artist_songs = {
        "T.I.": [
            *[make_song(f"a{i}.mp3", artist="T.I.", album="The KING") for i in range(15)],
            make_song("b.mp3", artist="T.I.", album="The King"),
        ]
    }

    recommendations = build_album_recommendations(album_groups_by_artist, artist_songs)

    candidates = recommendations[0]["candidates"]
    assert [c["album"] for c in candidates] == ["The KING", "The King"]
    assert len(candidates[0]["songs"]) == 15
    assert len(candidates[1]["songs"]) == 1


def test_build_album_recommendations_returns_empty_for_no_duplicates():
    assert build_album_recommendations({}, {}) == []
