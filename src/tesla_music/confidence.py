import unicodedata
from difflib import SequenceMatcher

# Below this length, a high similarity ratio is too easy to hit by chance
# (e.g. "Nas" vs "Nash" is 86% similar despite being different artists), so
# the fuzzy tier is skipped for short names.
FUZZY_MATCH_MIN_LENGTH = 6
FUZZY_MATCH_THRESHOLD = 0.90


def calculate_confidence(artist1, artist2):
    """
    Returns a confidence score and explanation
    for whether two artist names are likely duplicates.
    """

    if artist1 == artist2:
        return {
            "score": 100,
            "reason": "Exact match",
        }

    normalized1 = normalize(artist1)
    normalized2 = normalize(artist2)

    if normalized1 == normalized2:
        if artist1.lower() == artist2.lower():
            return {
                "score": 95,
                "reason": "Capitalization difference only",
            }

        if strip_accents(artist1.lower()) == strip_accents(artist2.lower()):
            return {
                "score": 95,
                "reason": "Accent difference only",
            }

        return {
            "score": 85,
            "reason": "Word order difference",
        }

    words1 = set(normalized1.split())
    words2 = set(normalized2.split())

    if words1 == words2:
        return {
            "score": 85,
            "reason": "Word order difference",
        }

    # Catches punctuation (R Kelly / R. Kelly, Lil Wayne / Lil' Wayne, T.I. /
    # TI) and compound-word spacing (Outkast / Out Kast, Sugarhill Gang /
    # Sugar Hill Gang) -- same letters in the same order once everything
    # but letters/digits is dropped, so this is still a near-certain match.
    key1 = _letters_only(artist1)
    key2 = _letters_only(artist2)

    if key1 == key2:
        return {
            "score": 90,
            "reason": "Punctuation or spacing difference only",
        }

    # Catches actual spelling variants (Missy Elliot / Missy Elliott) that
    # aren't the same letters in a different arrangement -- inherently a
    # guess, so this is scored low and meant to be reviewed, not trusted.
    # Skipped for names with digits: a digit difference ("Artist 0001" vs
    # "Artist 0002") is almost always a genuinely different, meaningful
    # identifier rather than a typo, and real stage names with numbers
    # ("50 Cent", "Blink-182", "Sum 41") should never be fuzzy-merged.
    if (
        min(len(key1), len(key2)) >= FUZZY_MATCH_MIN_LENGTH
        and key1.isalpha()
        and key2.isalpha()
    ):
        similarity = SequenceMatcher(None, key1, key2).ratio()

        if similarity >= FUZZY_MATCH_THRESHOLD:
            return {
                "score": 65,
                "reason": "Possible spelling variation — please review",
            }

    return {
        "score": 0,
        "reason": "No match",
    }


def _letters_only(name):
    name = strip_accents(name.lower())

    return "".join(char for char in name if char.isalnum())


def strip_accents(name):
    decomposed = unicodedata.normalize("NFKD", name)

    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize(name):
    name = name.lower()
    name = strip_accents(name)

    replacements = {
        "-": " ",
        "&": " ",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    words = name.split()

    return " ".join(sorted(words))
