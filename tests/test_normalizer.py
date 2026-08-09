from collections import Counter

from tesla_music.normalizer import find_album_duplicates_by_artist, find_similar_artists


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
