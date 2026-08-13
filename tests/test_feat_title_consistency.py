from tesla_music.feat_title_consistency import find_title_feat_spelling_fixes


def test_fixes_a_misspelled_feat_credit_against_a_known_artist(make_song):
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

    changes = find_title_feat_spelling_fixes(artist_songs)

    assert len(changes) == 1
    change = changes[0]
    assert change["file"] == "b.mp3"
    assert change["current_title"] == "Let It Go Remix (feat. Missy Elliot)"
    assert change["new_title"] == "Let It Go Remix (feat. Missy Elliott)"
    assert change["confidence"] == 65
    assert "Possible spelling variation" in change["reason"]


def test_fixes_only_the_mismatched_name_in_a_multi_artist_credit(make_song):
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

    changes = find_title_feat_spelling_fixes(artist_songs)

    assert len(changes) == 1
    assert changes[0]["new_title"] == (
        "Get Ur Freak On (feat. Nelly Furtado & Missy Elliott)"
    )


def test_ignores_a_feat_credit_that_already_matches_a_known_artist(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott")],
        "Someone": [
            make_song("c.mp3", artist="Someone", title="Already Correct (feat. Missy Elliott)")
        ],
    }

    assert find_title_feat_spelling_fixes(artist_songs) == []


def test_ignores_titles_with_no_feat_credit(make_song):
    artist_songs = {
        "Someone": [make_song("d.mp3", artist="Someone", title="No Feat Credit")],
    }

    assert find_title_feat_spelling_fixes(artist_songs) == []


def test_ignores_a_feat_credit_that_does_not_match_any_known_artist(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott")],
        "Someone": [
            make_song("e.mp3", artist="Someone", title="A Song (feat. Totally Unrelated Act)")
        ],
    }

    assert find_title_feat_spelling_fixes(artist_songs) == []


def test_does_not_touch_the_artist_tag(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott")],
        "Ciara": [
            make_song(
                "b.mp3",
                artist="Ciara",
                title="Let It Go Remix (feat. Missy Elliot)",
            )
        ],
    }

    changes = find_title_feat_spelling_fixes(artist_songs)

    assert "new_artist" not in changes[0]


def test_returns_empty_list_for_no_songs():
    assert find_title_feat_spelling_fixes({}) == []
