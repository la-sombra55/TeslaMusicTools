import re
from difflib import SequenceMatcher

from tesla_music.name_lists import join_names, split_multi_artist


# "feat."/"ft." (with the period actually present) allow zero or more
# spaces after -- a period is already an unambiguous separator, so
# "Feat.Swizz Beatz" (no space) needs to match too. "featuring"/"feat"/"ft"
# without a period still require at least one space, so a real name like
# "Featherstone" glued onto a following word never gets misread as a split.
FEAT_SPLIT_PATTERN = re.compile(
    r"\s*[\(\[]?\s*(?<!\w)(?:"
    r"featuring\s+"
    r"|feat\.\s*"
    r"|feat\s+"
    r"|ft\.\s*"
    r"|ft\s+"
    r")(.+?)\s*[\)\]]?$",
    re.IGNORECASE,
)

FEAT_MENTION_PATTERN = re.compile(
    r"\bfeaturing\b|\bfeat\b|\bft\b",
    re.IGNORECASE,
)

# Fuzzy fallback only covers the full word "featuring" (e.g. a misspelled
# "featurining"), not the short "feat"/"ft" abbreviations -- fuzzy-matching
# a 3-4 letter word is too easy to trigger on unrelated names by chance.
FEAT_KEYWORD_MIN_LENGTH = 6
FEAT_KEYWORD_FUZZY_THRESHOLD = 0.90


def split_featured_artist(artist):
    match = FEAT_SPLIT_PATTERN.search(artist)

    if match is not None:
        main_artist = artist[: match.start()].strip()
        featured_artist = match.group(1).strip()
    else:
        keyword_match = _find_fuzzy_featuring_keyword(artist)

        if keyword_match is None:
            return None

        main_artist = artist[: keyword_match.start()].strip()
        featured_artist = artist[keyword_match.end():].lstrip(" .:-").rstrip(" )]")

    if not main_artist or not featured_artist:
        return None

    return main_artist, featured_artist


def _find_fuzzy_featuring_keyword(artist):
    for word_match in re.finditer(r"[A-Za-z]+", artist):
        word = word_match.group()

        if len(word) < FEAT_KEYWORD_MIN_LENGTH:
            continue

        similarity = SequenceMatcher(None, word.lower(), "featuring").ratio()

        if similarity >= FEAT_KEYWORD_FUZZY_THRESHOLD:
            return word_match

    return None


def build_feat_title(title, featured_artist):
    existing = split_featured_artist(title)

    if existing is not None:
        base_title, existing_featured_text = existing
        existing_names = split_multi_artist(existing_featured_text) or [existing_featured_text]

        if featured_artist in existing_names:
            return title

        return f"{base_title} (feat. {join_names(existing_names + [featured_artist])})"

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
