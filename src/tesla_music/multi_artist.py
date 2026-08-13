from tesla_music.feat_normalizer import build_feat_title, split_featured_artist
from tesla_music.name_lists import SEPARATOR_AMPERSAND, SEPARATOR_SLASH, join_names, split_multi_artist

__all__ = [
    "SEPARATOR_AMPERSAND",
    "SEPARATOR_SLASH",
    "join_names",
    "split_multi_artist",
    "find_multi_artist_credits",
    "build_feature_choice",
    "build_separator_choice",
]


def find_multi_artist_credits(artist_songs):
    """
    Finds artist strings that look like multiple artists sharing one Artist
    tag (excluding anything the "featuring" cleanup already handles).
    """
    candidates = []

    for artist, songs in artist_songs.items():
        if split_featured_artist(artist) is not None:
            continue

        names = split_multi_artist(artist)

        if names is None:
            continue

        candidates.append(
            {
                "artist": artist,
                "candidates": names,
                "songs": songs,
            }
        )

    return candidates


def build_feature_choice(group, primary_index):
    """
    Splits a multi-artist group into: primary artist kept in the Artist
    field, everyone else appended to the Title as a featuring credit.
    """
    candidates = group["candidates"]
    primary_name = candidates[primary_index]
    remaining = candidates[:primary_index] + candidates[primary_index + 1:]
    featured_text = join_names(remaining)

    changes = []

    for song in group["songs"]:
        new_title = build_feat_title(song.title, featured_text)

        changes.append(
            {
                "file": str(song.path),
                "current_artist": group["artist"],
                "new_artist": primary_name,
                "current_title": song.title,
                "new_title": new_title,
                "confidence": 100,
                "reason": (
                    f"Split multi-artist credit — kept '{primary_name}', "
                    f"featured '{featured_text}'"
                ),
            }
        )

    return changes


def build_separator_choice(group, separator):
    """
    Rewrites a multi-artist group's Artist tag using a single consistent
    separator between all the parsed names.
    """
    new_artist = separator.join(group["candidates"])

    if new_artist == group["artist"]:
        return []

    changes = []

    for song in group["songs"]:
        changes.append(
            {
                "file": str(song.path),
                "current_artist": group["artist"],
                "new_artist": new_artist,
                "confidence": 100,
                "reason": f"Normalized multi-artist separator to {separator.strip()!r}",
            }
        )

    return changes
