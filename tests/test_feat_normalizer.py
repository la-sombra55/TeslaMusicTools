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


def test_split_featured_artist_does_not_match_ft_fused_inside_a_word():
    # Regression test: "Daft Punk" contains "ft" as a substring ("Da" + "ft"),
    # which was previously misdetected as "Da" featuring "Punk".
    assert split_featured_artist("Daft Punk") is None


def test_split_featured_artist_does_not_match_feat_fused_inside_a_word():
    assert split_featured_artist("Defeat Devices") is None


def test_split_featured_artist_handles_feat_period_with_no_space():
    # Regression test: "Feat.Swizz Beatz" has no space after the period.
    assert split_featured_artist("Busta Rhymes Feat.Swizz Beatz") == (
        "Busta Rhymes",
        "Swizz Beatz",
    )


def test_split_featured_artist_handles_ft_period_with_no_space():
    assert split_featured_artist("Busta Rhymes Ft.Swizz Beatz") == (
        "Busta Rhymes",
        "Swizz Beatz",
    )


def test_split_featured_artist_handles_a_misspelled_featuring():
    # Regression test: "featurining" (extra "in") wasn't caught by the
    # exact keyword pattern.
    assert split_featured_artist("Fabolous featurining Ransom") == ("Fabolous", "Ransom")


def test_split_featured_artist_fuzzy_fallback_does_not_match_a_real_name():
    # "Featherstone" is textually close to "featuring" but is a real name,
    # not a typo of it -- and even if it were flagged, there'd be no
    # featured-artist text left to split off.
    assert split_featured_artist("Featherstone") is None
    assert split_featured_artist("XYZ Featherstone") is None


def test_build_feat_title_appends_when_missing():
    assert build_feat_title("Girls Like You", "Cardi B") == "Girls Like You (feat. Cardi B)"


def test_build_feat_title_leaves_title_unchanged_if_already_present():
    title = "Girls Like You (feat. Cardi B)"
    assert build_feat_title(title, "Cardi B") == title


def test_build_feat_title_merges_into_an_existing_feat_list_with_other_names():
    # Regression test: a title already crediting other featured artists was
    # wrongly left untouched instead of adding this one to the list.
    title = (
        "This Is Family (Bonus Track) (feat. Freck Billionaire, Red Cafe, "
        "Joe Budden & Paul Cain)"
    )

    result = build_feat_title(title, "Ransom")

    assert result == (
        "This Is Family (Bonus Track) (feat. Freck Billionaire, Red Cafe, "
        "Joe Budden, Paul Cain & Ransom)"
    )


def test_build_feat_title_does_not_duplicate_an_already_credited_name():
    title = "Girls Like You (feat. Cardi B & Offset)"
    assert build_feat_title(title, "Cardi B") == title


def test_build_feat_title_merges_into_a_single_existing_featured_name():
    title = "Girls Like You (feat. Cardi B)"
    assert build_feat_title(title, "Offset") == "Girls Like You (feat. Cardi B & Offset)"


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
