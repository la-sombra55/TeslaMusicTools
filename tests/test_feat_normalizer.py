from tesla_music.feat_normalizer import (
    build_feat_title,
    find_featured_artist_changes,
    split_featured_artist,
)


def test_split_featured_artist_handles_featuring():
    assert split_featured_artist("Maroon 5 featuring Cardi B") == ("Maroon 5", "Cardi B")


def test_split_featured_artist_handles_feat_with_period():
    assert split_featured_artist("Maroon 5 feat. Cardi B") == ("Maroon 5", "Cardi B")


def test_split_featured_artist_handles_parenthesized_feat():
    assert split_featured_artist("Maroon 5 (feat. Cardi B)") == ("Maroon 5", "Cardi B")


def test_split_featured_artist_handles_ft():
    assert split_featured_artist("Maroon 5 ft. Cardi B") == ("Maroon 5", "Cardi B")


def test_split_featured_artist_returns_none_when_no_match():
    assert split_featured_artist("Chris Brown & Tyga") is None
    assert split_featured_artist("Jay-Z & Kanye West") is None


def test_build_feat_title_appends_when_missing():
    assert build_feat_title("Girls Like You", "Cardi B") == "Girls Like You (feat. Cardi B)"


def test_build_feat_title_leaves_title_unchanged_if_already_present():
    title = "Girls Like You (feat. Cardi B)"
    assert build_feat_title(title, "Cardi B") == title


def test_find_featured_artist_changes_produces_one_change_per_song(make_song):
    artist_songs = {
        "Maroon 5 featuring Cardi B": [
            make_song("a.mp3", artist="Maroon 5 featuring Cardi B", title="Girls Like You"),
        ],
        "Chris Brown": [make_song("b.mp3", artist="Chris Brown", title="Deuces")],
    }

    changes = find_featured_artist_changes(artist_songs)

    assert len(changes) == 1
    change = changes[0]
    assert change["file"] == "a.mp3"
    assert change["current_artist"] == "Maroon 5 featuring Cardi B"
    assert change["new_artist"] == "Maroon 5"
    assert change["current_title"] == "Girls Like You"
    assert change["new_title"] == "Girls Like You (feat. Cardi B)"
    assert change["confidence"] == 100


def test_find_featured_artist_changes_returns_empty_for_clean_library(make_song):
    artist_songs = {
        "Chris Brown": [make_song("b.mp3", artist="Chris Brown", title="Deuces")],
    }

    assert find_featured_artist_changes(artist_songs) == []
