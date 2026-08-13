from tesla_music.confidence import calculate_confidence
from tesla_music.feat_normalizer import build_feat_title, split_featured_artist
from tesla_music.multi_artist import join_names, split_multi_artist


def find_title_feat_spelling_fixes(artist_songs):
    """
    Finds featured-artist credits already embedded in a song's Title (e.g.
    "(feat. Missy Elliot)") that use a different spelling than that same
    artist's current spelling elsewhere in the library's Artist tags, and
    proposes correcting just the credited name -- the rest of the title and
    the song's own Artist tag are left untouched.
    """
    known_artists = list(artist_songs.keys())
    changes = []

    for songs in artist_songs.values():
        for song in songs:
            split = split_featured_artist(song.title)

            if split is None:
                continue

            base_title, featured_text = split
            featured_names = split_multi_artist(featured_text) or [featured_text]

            corrected_names = []
            weakest_confidence = None

            for name in featured_names:
                match = _best_artist_match(name, known_artists)

                if match is None:
                    corrected_names.append(name)
                    continue

                matched_artist, confidence = match
                corrected_names.append(matched_artist)

                if weakest_confidence is None or confidence["score"] < weakest_confidence["score"]:
                    weakest_confidence = confidence

            if corrected_names == featured_names:
                continue

            new_title = build_feat_title(base_title, join_names(corrected_names))

            changes.append(
                {
                    "file": str(song.path),
                    "current_title": song.title,
                    "new_title": new_title,
                    "confidence": weakest_confidence["score"],
                    "reason": f"Featured-credit spelling — {weakest_confidence['reason']}",
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
