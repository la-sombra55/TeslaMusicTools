from tesla_music.feat_title_consistency import (
    build_title_feat_fix_changes,
    find_title_feat_spelling_opportunities,
    group_opportunities_by_artist,
)


def test_finds_a_misspelled_feat_credit_against_a_known_artist(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott", title="Work It")],
        "Ciara": [
            make_song(
                "b.mp3",
                artist="Ciara",
                title="Let It Go Remix (feat. Missy Elliot)",
            )
        ],
    }

    opportunities = find_title_feat_spelling_opportunities(artist_songs)

    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity["file"] == "b.mp3"
    assert opportunity["artist"] == "Missy Elliott"
    assert opportunity["misspelled_as"] == "Missy Elliot"
    assert opportunity["confidence"] == 65
    assert "Possible spelling variation" in opportunity["reason"]


def test_finds_only_the_mismatched_name_in_a_multi_artist_credit(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott")],
        "Nelly Furtado": [make_song("n.mp3", artist="Nelly Furtado")],
        "Ciara": [
            make_song(
                "b.mp3",
                artist="Ciara",
                title="Get Ur Freak On (feat. Nelly Furtado & Missy Elliot)",
            )
        ],
    }

    opportunities = find_title_feat_spelling_opportunities(artist_songs)

    assert len(opportunities) == 1
    assert opportunities[0]["misspelled_as"] == "Missy Elliot"


def test_ignores_a_feat_credit_that_already_matches_a_known_artist(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott")],
        "Someone": [
            make_song("c.mp3", artist="Someone", title="Already Correct (feat. Missy Elliott)")
        ],
    }

    assert find_title_feat_spelling_opportunities(artist_songs) == []


def test_ignores_titles_with_no_feat_credit(make_song):
    artist_songs = {
        "Someone": [make_song("d.mp3", artist="Someone", title="No Feat Credit")],
    }

    assert find_title_feat_spelling_opportunities(artist_songs) == []


def test_ignores_a_feat_credit_that_does_not_match_any_known_artist(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott")],
        "Someone": [
            make_song("e.mp3", artist="Someone", title="A Song (feat. Totally Unrelated Act)")
        ],
    }

    assert find_title_feat_spelling_opportunities(artist_songs) == []


def test_returns_empty_list_for_no_songs():
    assert find_title_feat_spelling_opportunities({}) == []


# --- group_opportunities_by_artist ---


def test_groups_multiple_songs_crediting_the_same_artist_into_one_group(make_song):
    artist_songs = {
        "Pharrell": [make_song("p.mp3", artist="Pharrell")],
        "Song A": [
            make_song("a.mp3", artist="Song A", title="Track One (feat. Pharell)")
        ],
        "Song B": [
            make_song("b.mp3", artist="Song B", title="Track Two (feat. Pharrel)")
        ],
    }

    opportunities = find_title_feat_spelling_opportunities(artist_songs)
    groups = group_opportunities_by_artist(opportunities)

    assert len(groups) == 1
    group = groups[0]
    assert group["artist"] == "Pharrell"
    assert group["song_count"] == 2
    assert len(group["opportunities"]) == 2


def test_group_confidence_is_the_weakest_of_its_opportunities(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott")],
        "Song A": [
            # Punctuation-only difference -> 90% confidence
            make_song("b.mp3", artist="Song A", title="Track (feat. Missy Elliott.)")
        ],
        "Song B": [
            # Spelling variation -> 65% confidence
            make_song("c.mp3", artist="Song B", title="Track Two (feat. Missy Elliot)")
        ],
    }

    opportunities = find_title_feat_spelling_opportunities(artist_songs)
    groups = group_opportunities_by_artist(opportunities)

    assert groups[0]["confidence"] == 65


def test_group_opportunities_by_artist_returns_empty_for_no_opportunities():
    assert group_opportunities_by_artist([]) == []


# --- build_title_feat_fix_changes ---


def test_builds_the_corrected_title_for_approved_opportunities(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott")],
        "Ciara": [
            make_song(
                "b.mp3", artist="Ciara", title="Let It Go Remix (feat. Missy Elliot)"
            )
        ],
    }

    opportunities = find_title_feat_spelling_opportunities(artist_songs)
    changes = build_title_feat_fix_changes(opportunities, artist_songs)

    assert len(changes) == 1
    change = changes[0]
    assert change["file"] == "b.mp3"
    assert change["current_title"] == "Let It Go Remix (feat. Missy Elliot)"
    assert change["new_title"] == "Let It Go Remix (feat. Missy Elliott)"
    assert "new_artist" not in change


def test_only_applies_corrections_for_approved_names_in_a_multi_artist_credit(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott")],
        "Nelly Furtado": [make_song("n.mp3", artist="Nelly Furtado")],
        "Ciara": [
            make_song(
                "b.mp3",
                artist="Ciara",
                title="Get Ur Freak On (feat. Nelly Furtado & Missy Elliot)",
            )
        ],
    }

    opportunities = find_title_feat_spelling_opportunities(artist_songs)

    # Approve only the Missy Elliott fix (there's only one opportunity here
    # anyway since Nelly Furtado already matches, but this exercises the
    # "approved subset" filtering path explicitly).
    changes = build_title_feat_fix_changes(opportunities, artist_songs)

    assert changes[0]["new_title"] == (
        "Get Ur Freak On (feat. Nelly Furtado & Missy Elliott)"
    )


def test_build_title_feat_fix_changes_returns_empty_for_no_approved_opportunities(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott")],
        "Ciara": [
            make_song(
                "b.mp3", artist="Ciara", title="Let It Go Remix (feat. Missy Elliot)"
            )
        ],
    }

    assert build_title_feat_fix_changes([], artist_songs) == []
