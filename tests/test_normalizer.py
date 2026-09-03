from collections import Counter

from tesla_music.normalizer import (
    find_album_duplicates_by_artist,
    find_similar_artists,
    find_similar_genres,
)


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


def test_find_similar_artists_clusters_more_than_two_transitively_similar_variants():
    # Three spellings of the same artist should produce one merged cluster,
    # not three overlapping pairwise groups (A~B, A~C, B~C).
    artists = Counter({"Missy Elliot": 12, "Missy Elliott": 8, "MISSY ELLIOTT": 3})

    groups = find_similar_artists(artists)

    assert len(groups) == 1
    group = groups[0]
    assert {a["artist"] for a in group["artists"]} == {
        "Missy Elliot",
        "Missy Elliott",
        "MISSY ELLIOTT",
    }


def test_find_similar_artists_uses_the_weakest_edge_confidence_in_a_cluster():
    # "Missy Elliot"/"Missy Elliott" is only a 65%-confidence spelling
    # guess, so the whole cluster should reflect that lower confidence
    # even though "Missy Elliott"/"MISSY ELLIOTT" is a 95% case match.
    artists = Counter({"Missy Elliot": 12, "Missy Elliott": 8, "MISSY ELLIOTT": 3})

    groups = find_similar_artists(artists)

    assert groups[0]["score"] == 65
    assert groups[0]["reason"] == "Possible spelling variation — please review"


def test_find_similar_artists_does_not_group_distinct_artists():
    artists = Counter({"Chris Brown": 97, "Chris Brown & Tyga": 18, "50 Cent": 1})

    groups = find_similar_artists(artists)

    assert groups == []


def test_find_similar_artists_returns_empty_for_empty_input():
    assert find_similar_artists(Counter()) == []


def test_find_similar_genres_groups_spacing_and_case_variants():
    genres = Counter({"Hip-Hop": 120, "Hip Hop": 15, "hip hop": 8, "HIPHOP": 3})

    groups = find_similar_genres(genres)

    assert len(groups) == 1
    group = groups[0]
    assert {g["genre"] for g in group["genres"]} == {"Hip-Hop", "Hip Hop", "hip hop", "HIPHOP"}
    assert group["score"] > 0


def test_find_similar_genres_groups_ampersand_spacing_variants():
    genres = Counter({"R&B": 40, "R & B": 6, "r&b": 2})

    groups = find_similar_genres(genres)

    assert len(groups) == 1
    assert {g["genre"] for g in groups[0]["genres"]} == {"R&B", "R & B", "r&b"}


def test_find_similar_genres_does_not_group_distinct_genres():
    genres = Counter({"Pop": 30, "Rock": 25, "Jazz": 10})

    assert find_similar_genres(genres) == []


def test_find_similar_genres_returns_empty_for_empty_input():
    assert find_similar_genres(Counter()) == []


def test_find_album_duplicates_by_artist_groups_case_variants(make_song):
    artist_songs = {
        "T.I.": [
            *[make_song(f"a{i}.mp3", artist="T.I.", album="The KING") for i in range(15)],
            make_song("b.mp3", artist="T.I.", album="The King"),
        ]
    }

    duplicates = find_album_duplicates_by_artist(artist_songs)

    assert list(duplicates.keys()) == ["T.I."]
    groups = duplicates["T.I."]
    assert len(groups) == 1
    assert {a["album"] for a in groups[0]["albums"]} == {"The KING", "The King"}
    assert groups[0]["score"] == 95


def test_find_album_duplicates_by_artist_does_not_cross_different_artists(make_song):
    # Two different artists sharing an album title should never be compared
    # to each other.
    artist_songs = {
        "Artist A": [make_song("a.mp3", artist="Artist A", album="Greatest Hits")],
        "Artist B": [make_song("b.mp3", artist="Artist B", album="Greatest Hits")],
    }

    duplicates = find_album_duplicates_by_artist(artist_songs)

    assert duplicates == {}


def test_find_album_duplicates_by_artist_skips_artists_with_no_duplicates(make_song):
    artist_songs = {
        "Chris Brown": [
            make_song("a.mp3", artist="Chris Brown", album="Fortune"),
            make_song("b.mp3", artist="Chris Brown", album="F.A.M.E."),
        ]
    }

    assert find_album_duplicates_by_artist(artist_songs) == {}


def test_find_album_duplicates_by_artist_returns_empty_for_empty_input():
    assert find_album_duplicates_by_artist({}) == {}
