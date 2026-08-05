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

    return {
        "score": 0,
        "reason": "No match",
    }


def normalize(name):
    name = name.lower()

    replacements = {
        "-": " ",
        "&": " ",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    words = name.split()

    return " ".join(sorted(words))