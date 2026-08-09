from tesla_music.multi_artist import (
    SEPARATOR_AMPERSAND,
    SEPARATOR_SLASH,
    build_feature_choice,
    build_separator_choice,
    find_multi_artist_credits,
    split_multi_artist,
)


# --- split_multi_artist ---


def test_split_multi_artist_handles_ampersand():
    assert split_multi_artist("Beyoncé & Stevie Wonder") == ["Beyoncé", "Stevie Wonder"]


def test_split_multi_artist_handles_comma_and_ampersand_list():
    result = split_multi_artist("Kanye West, Beyoncé, Charlie Wilson & Big Sean")
    assert result == ["Kanye West", "Beyoncé", "Charlie Wilson", "Big Sean"]


def test_split_multi_artist_handles_comma_and_the_word_and():
    assert split_multi_artist("Earth,Wind,and Fire") == ["Earth", "Wind", "Fire"]


def test_split_multi_artist_handles_plain_and_between_two_names():
    assert split_multi_artist("Simon and Garfunkel") == ["Simon", "Garfunkel"]


def test_split_multi_artist_handles_slash():
    result = split_multi_artist("Fabolous/P. Diddy/Jagged Edge")
    assert result == ["Fabolous", "P. Diddy", "Jagged Edge"]


def test_split_multi_artist_handles_vs():
    assert split_multi_artist("Freddie vs. Jason") == ["Freddie", "Jason"]


def test_split_multi_artist_returns_none_for_a_single_artist():
    assert split_multi_artist("Chris Brown") is None


def test_split_multi_artist_false_positive_on_a_real_band_name_is_expected():
    # Known limitation: a real band name containing "and" parses as two
    # names. This is why nothing is ever auto-applied for this feature --
    # the user reviews and picks "keep as-is" for cases like this.
    assert split_multi_artist("The Naked and Famous") == ["The Naked", "Famous"]


# --- find_multi_artist_credits ---


def test_find_multi_artist_credits_finds_ampersand_credit(make_song):
    artist_songs = {
        "Beyoncé & Stevie Wonder": [
            make_song("a.mp3", artist="Beyoncé & Stevie Wonder", title="Ave Maria")
        ],
    }

    candidates = find_multi_artist_credits(artist_songs)

    assert len(candidates) == 1
    assert candidates[0]["artist"] == "Beyoncé & Stevie Wonder"
    assert candidates[0]["candidates"] == ["Beyoncé", "Stevie Wonder"]
    assert len(candidates[0]["songs"]) == 1


def test_find_multi_artist_credits_excludes_single_artists(make_song):
    artist_songs = {"Chris Brown": [make_song("a.mp3", artist="Chris Brown")]}

    assert find_multi_artist_credits(artist_songs) == []


def test_find_multi_artist_credits_excludes_credits_already_handled_by_feat_cleanup(make_song):
    artist_songs = {
        "Chris Brown Featuring T-Pain & Nelly": [
            make_song("a.mp3", artist="Chris Brown Featuring T-Pain & Nelly")
        ],
    }

    assert find_multi_artist_credits(artist_songs) == []


# --- build_feature_choice ---


def test_build_feature_choice_keeps_primary_and_features_the_rest(make_song):
    group = {
        "artist": "Beyoncé & Stevie Wonder",
        "candidates": ["Beyoncé", "Stevie Wonder"],
        "songs": [make_song("a.mp3", artist="Beyoncé & Stevie Wonder", title="Ave Maria")],
    }

    changes = build_feature_choice(group, primary_index=0)

    assert changes == [
        {
            "file": "a.mp3",
            "current_artist": "Beyoncé & Stevie Wonder",
            "new_artist": "Beyoncé",
            "current_title": "Ave Maria",
            "new_title": "Ave Maria (feat. Stevie Wonder)",
            "confidence": 100,
            "reason": (
                "Split multi-artist credit — kept 'Beyoncé', "
                "featured 'Stevie Wonder'"
            ),
        }
    ]


def test_build_feature_choice_can_pick_the_second_artist_as_primary(make_song):
    group = {
        "artist": "Beyoncé & Stevie Wonder",
        "candidates": ["Beyoncé", "Stevie Wonder"],
        "songs": [make_song("a.mp3", artist="Beyoncé & Stevie Wonder", title="Ave Maria")],
    }

    changes = build_feature_choice(group, primary_index=1)

    assert changes[0]["new_artist"] == "Stevie Wonder"
    assert changes[0]["new_title"] == "Ave Maria (feat. Beyoncé)"


def test_build_feature_choice_joins_multiple_remaining_artists(make_song):
    group = {
        "artist": "Kanye West, Beyoncé, Charlie Wilson & Big Sean",
        "candidates": ["Kanye West", "Beyoncé", "Charlie Wilson", "Big Sean"],
        "songs": [make_song("a.mp3", title="Ghost Town")],
    }

    changes = build_feature_choice(group, primary_index=0)

    assert changes[0]["new_artist"] == "Kanye West"
    assert changes[0]["new_title"] == "Ghost Town (feat. Beyoncé, Charlie Wilson & Big Sean)"


def test_build_feature_choice_applies_to_every_song_in_the_group(make_song):
    group = {
        "artist": "Chris Brown & Tyga",
        "candidates": ["Chris Brown", "Tyga"],
        "songs": [
            make_song("a.mp3", title="Song A"),
            make_song("b.mp3", title="Song B"),
        ],
    }

    changes = build_feature_choice(group, primary_index=0)

    assert len(changes) == 2
    assert [c["file"] for c in changes] == ["a.mp3", "b.mp3"]
    assert all(c["new_artist"] == "Chris Brown" for c in changes)


# --- build_separator_choice ---


def test_build_separator_choice_rejoins_with_ampersand(make_song):
    group = {
        "artist": "Fabolous/P. Diddy/Jagged Edge",
        "candidates": ["Fabolous", "P. Diddy", "Jagged Edge"],
        "songs": [make_song("a.mp3")],
    }

    changes = build_separator_choice(group, SEPARATOR_AMPERSAND)

    assert changes == [
        {
            "file": "a.mp3",
            "current_artist": "Fabolous/P. Diddy/Jagged Edge",
            "new_artist": "Fabolous & P. Diddy & Jagged Edge",
            "confidence": 100,
            "reason": "Normalized multi-artist separator to '&'",
        }
    ]


def test_build_separator_choice_rejoins_with_slash(make_song):
    group = {
        "artist": "Beyoncé & Stevie Wonder",
        "candidates": ["Beyoncé", "Stevie Wonder"],
        "songs": [make_song("a.mp3")],
    }

    changes = build_separator_choice(group, SEPARATOR_SLASH)

    assert changes[0]["new_artist"] == "Beyoncé / Stevie Wonder"


def test_build_separator_choice_is_a_no_op_when_already_in_that_format(make_song):
    group = {
        "artist": "Beyoncé & Stevie Wonder",
        "candidates": ["Beyoncé", "Stevie Wonder"],
        "songs": [make_song("a.mp3")],
    }

    changes = build_separator_choice(group, SEPARATOR_AMPERSAND)

    assert changes == []
