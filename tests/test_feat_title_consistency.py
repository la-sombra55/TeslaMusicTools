from tesla_music.feat_title_consistency import (
    build_artist_spelling_changes,
    find_artist_spelling_groups,
)


def _spelling_counts(group):
    return {s["spelling"]: len(s["mentions"]) for s in group["spellings"]}


def test_groups_artist_tag_and_title_feat_spellings_together(make_song):
    artist_songs = {
        "JILL SCOTT": [make_song("a.mp3", artist="JILL SCOTT")],
        "Ciara": [
            make_song("b.mp3", artist="Ciara", title="Song One (feat. Jill Scott)")
        ],
        "Erykah Badu": [
            make_song("c.mp3", artist="Erykah Badu", title="Song Two (feat. Jill Scot)")
        ],
    }

    groups = find_artist_spelling_groups(artist_songs)

    assert len(groups) == 1
    group = groups[0]
    assert _spelling_counts(group) == {"JILL SCOTT": 1, "Jill Scott": 1, "Jill Scot": 1}
    assert group["total_count"] == 3


def test_spellings_are_sorted_by_mention_count_descending(make_song):
    artist_songs = {
        "JILL SCOTT": [
            make_song("a.mp3", artist="JILL SCOTT"),
            make_song("b.mp3", artist="JILL SCOTT"),
        ],
        "Ciara": [
            make_song("c.mp3", artist="Ciara", title="Song One (feat. Jill Scott)")
        ],
    }

    groups = find_artist_spelling_groups(artist_songs)

    assert [s["spelling"] for s in groups[0]["spellings"]] == ["JILL SCOTT", "Jill Scott"]


def test_excludes_clusters_with_no_featured_credit_involved(make_song):
    # A pure Artist-tag-vs-Artist-tag mismatch (no title credit involved) is
    # Duplicate Artist's job, not this tool's -- shouldn't show up here.
    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown")],
        "chris brown": [make_song("b.mp3", artist="chris brown")],
    }

    assert find_artist_spelling_groups(artist_songs) == []


def test_excludes_a_feat_credit_that_already_matches_the_only_known_spelling(make_song):
    artist_songs = {
        "Missy Elliott": [make_song("a.mp3", artist="Missy Elliott")],
        "Someone": [
            make_song("c.mp3", artist="Someone", title="Already Correct (feat. Missy Elliott)")
        ],
    }

    assert find_artist_spelling_groups(artist_songs) == []


def test_returns_empty_list_for_no_songs():
    assert find_artist_spelling_groups({}) == []


# --- build_artist_spelling_changes ---


def test_builds_artist_tag_and_title_changes_for_the_preferred_spelling(make_song):
    artist_songs = {
        "JILL SCOTT": [make_song("a.mp3", artist="JILL SCOTT", title="Golden")],
        "Ciara": [
            make_song("b.mp3", artist="Ciara", title="Song One (feat. Jill Scott)")
        ],
        "Erykah Badu": [
            make_song("c.mp3", artist="Erykah Badu", title="Song Two (feat. Jill Scot)")
        ],
    }

    groups = find_artist_spelling_groups(artist_songs)
    changes = build_artist_spelling_changes("Jill Scott", groups[0], artist_songs)

    changes_by_file = {c["file"]: c for c in changes}

    assert changes_by_file["a.mp3"]["current_artist"] == "JILL SCOTT"
    assert changes_by_file["a.mp3"]["new_artist"] == "Jill Scott"
    assert "new_title" not in changes_by_file["a.mp3"]

    assert changes_by_file["c.mp3"]["current_title"] == "Song Two (feat. Jill Scot)"
    assert changes_by_file["c.mp3"]["new_title"] == "Song Two (feat. Jill Scott)"
    assert "new_artist" not in changes_by_file["c.mp3"]

    # b.mp3 already says "Jill Scott" in its title credit -- nothing to fix.
    assert "b.mp3" not in changes_by_file


def test_no_changes_needed_when_preferred_spelling_is_already_used_everywhere(make_song):
    artist_songs = {
        "JILL SCOTT": [make_song("a.mp3", artist="JILL SCOTT")],
        "Ciara": [
            make_song("b.mp3", artist="Ciara", title="Song One (feat. Jill Scott)")
        ],
    }

    groups = find_artist_spelling_groups(artist_songs)
    changes = build_artist_spelling_changes("JILL SCOTT", groups[0], artist_songs)

    changes_by_file = {c["file"]: c for c in changes}
    assert "a.mp3" not in changes_by_file
    assert changes_by_file["b.mp3"]["new_title"] == "Song One (feat. JILL SCOTT)"


def test_only_corrects_the_matching_name_in_a_multi_artist_title_credit(make_song):
    artist_songs = {
        "Jill Scott": [make_song("a.mp3", artist="Jill Scott")],
        "Nelly Furtado": [make_song("n.mp3", artist="Nelly Furtado")],
        "Ciara": [
            make_song(
                "b.mp3",
                artist="Ciara",
                title="Song One (feat. Nelly Furtado & Jill Scot)",
            )
        ],
    }

    groups = find_artist_spelling_groups(artist_songs)
    changes = build_artist_spelling_changes("Jill Scott", groups[0], artist_songs)

    change = next(c for c in changes if c["file"] == "b.mp3")
    assert change["new_title"] == "Song One (feat. Nelly Furtado & Jill Scott)"
