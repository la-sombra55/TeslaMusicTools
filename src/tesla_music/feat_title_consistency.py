from collections import defaultdict

from tesla_music.confidence import calculate_confidence
from tesla_music.feat_normalizer import build_feat_title, split_featured_artist
from tesla_music.multi_artist import join_names, split_multi_artist


def find_title_feat_spelling_opportunities(artist_songs):
    """
    Finds featured-artist credits embedded in a song's Title (e.g. "(feat.
    Missy Elliot)") that use a different spelling than that same artist's
    current spelling elsewhere in the library's Artist tags.

    Returns one entry per (song, misspelled name) pair, without building the
    corrected title yet -- a title can credit more than one artist, so the
    actual rewrite depends on which artists the user chooses to normalize
    (see build_title_feat_fix_changes).
    """
    known_artists = list(artist_songs.keys())
    opportunities = []

    for songs in artist_songs.values():
        for song in songs:
            split = split_featured_artist(song.title)

            if split is None:
                continue

            _, featured_text = split
            featured_names = split_multi_artist(featured_text) or [featured_text]

            for name in featured_names:
                match = _best_artist_match(name, known_artists)

                if match is None:
                    continue

                matched_artist, confidence = match

                opportunities.append(
                    {
                        "file": str(song.path),
                        "artist": matched_artist,
                        "misspelled_as": name,
                        "confidence": confidence["score"],
                        "reason": confidence["reason"],
                    }
                )

    return opportunities


def group_opportunities_by_artist(opportunities):
    """
    Groups per-song opportunities by the canonical artist they'd be
    normalized to, so the UI can offer one choice per artist ("12 songs
    credit Pharrell under a different spelling") instead of one per song.
    """
    by_artist = defaultdict(list)

    for opportunity in opportunities:
        by_artist[opportunity["artist"]].append(opportunity)

    groups = []

    for artist, items in by_artist.items():
        weakest = min(items, key=lambda o: o["confidence"])

        groups.append(
            {
                "artist": artist,
                "song_count": len({item["file"] for item in items}),
                "confidence": weakest["confidence"],
                "reason": weakest["reason"],
                "opportunities": items,
            }
        )

    return sorted(groups, key=lambda g: g["artist"])


def build_title_feat_fix_changes(approved_opportunities, artist_songs):
    """
    Builds the actual title changes for an approved set of opportunities
    (as returned by find_title_feat_spelling_opportunities). Grouped by
    file since one title can end up with more than one corrected name.
    """
    song_by_file = {
        str(song.path): song for songs in artist_songs.values() for song in songs
    }

    corrections_by_file = defaultdict(dict)
    opportunities_by_file = defaultdict(list)

    for opportunity in approved_opportunities:
        file = opportunity["file"]
        corrections_by_file[file][opportunity["misspelled_as"]] = opportunity["artist"]
        opportunities_by_file[file].append(opportunity)

    changes = []

    for file, corrections in corrections_by_file.items():
        song = song_by_file[file]
        base_title, featured_text = split_featured_artist(song.title)
        featured_names = split_multi_artist(featured_text) or [featured_text]

        corrected_names = [corrections.get(name, name) for name in featured_names]

        if corrected_names == featured_names:
            continue

        new_title = build_feat_title(base_title, join_names(corrected_names))
        weakest = min(opportunities_by_file[file], key=lambda o: o["confidence"])

        changes.append(
            {
                "file": file,
                "current_title": song.title,
                "new_title": new_title,
                "confidence": weakest["confidence"],
                "reason": weakest["reason"],
            }
        )

    return changes


def _best_artist_match(name, known_artists):
    if name in known_artists:
        return None

    best = None

    for artist in known_artists:
        if artist == name:
            continue

        confidence = calculate_confidence(name, artist)

        if confidence["score"] > 0 and (best is None or confidence["score"] > best[1]["score"]):
            best = (artist, confidence)

    return best
