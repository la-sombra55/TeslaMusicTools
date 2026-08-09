import re


FEAT_SPLIT_PATTERN = re.compile(
    r"\s*[\(\[]?\s*(?<!\w)(?:featuring|feat\.?|ft\.?)\s+(.+?)\s*[\)\]]?$",
    re.IGNORECASE,
)

FEAT_MENTION_PATTERN = re.compile(
    r"\bfeaturing\b|\bfeat\b|\bft\b",
    re.IGNORECASE,
)


def split_featured_artist(artist):
    match = FEAT_SPLIT_PATTERN.search(artist)

    if match is None:
        return None

    main_artist = artist[: match.start()].strip()
    featured_artist = match.group(1).strip()

    if not main_artist or not featured_artist:
        return None

    return main_artist, featured_artist


def build_feat_title(title, featured_artist):
    if FEAT_MENTION_PATTERN.search(title):
        return title

    return f"{title} (feat. {featured_artist})"


def find_featured_artist_changes(artist_songs):
    changes = []

    for artist, songs in artist_songs.items():
        split = split_featured_artist(artist)

        if split is None:
            continue

        main_artist, featured_artist = split

        for song in songs:
            new_title = build_feat_title(song.title, featured_artist)

            changes.append(
                {
                    "file": str(song.path),
                    "current_artist": artist,
                    "new_artist": main_artist,
                    "current_title": song.title,
                    "new_title": new_title,
                    "confidence": 100,
                    "reason": f"Featured artist '{featured_artist}' moved from Artist tag to Title tag",
                }
            )

    return changes
