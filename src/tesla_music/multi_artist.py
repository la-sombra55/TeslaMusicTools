import re

from tesla_music.feat_normalizer import build_feat_title, split_featured_artist

SEPARATOR_AMPERSAND = " & "
SEPARATOR_SLASH = " / "


_SEPARATOR_PATTERN = re.compile(r"&|\band\b|\bwith\b|/|\s+vs\.?\s+", re.IGNORECASE)


def split_multi_artist(artist):
    """
    Parses an artist string into individual artist names when it looks like
    a multi-artist credit joined by '&', ',', 'and', 'with', '/', or 'vs'.
    Separators inside parentheses are ignored -- parenthetical text is
    usually a note (e.g. "(Akon Intro)"), not a second artist, and splitting
    on a comma in there produces mismatched parens in the result. Returns
    None when fewer than two top-level names are found.
    """
    pieces = []
    current = ""
    depth = 0
    i = 0

    while i < len(artist):
        char = artist[i]

        if char == "(":
            depth += 1
            current += char
            i += 1
        elif char == ")":
            depth = max(0, depth - 1)
            current += char
            i += 1
        elif depth == 0 and char == ",":
            pieces.append(current)
            current = ""
            i += 1
        elif depth == 0 and (match := _SEPARATOR_PATTERN.match(artist, i)):
            pieces.append(current)
            current = ""
            i = match.end()
        else:
            current += char
            i += 1

    pieces.append(current)

    names = [name.strip() for name in pieces]
    names = [name for name in names if name]

    if len(names) < 2:
        return None

    return names


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


def join_names(names):
    if len(names) == 1:
        return names[0]

    return ", ".join(names[:-1]) + " & " + names[-1]


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
