import re

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


def join_names(names):
    if len(names) == 1:
        return names[0]

    return ", ".join(names[:-1]) + " & " + names[-1]
