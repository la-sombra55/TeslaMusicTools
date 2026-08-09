from pathlib import Path


def mirrored_path(file_path):
    """
    Returns file_path made relative (stripping any absolute anchor), so it
    can be joined under a different root folder without colliding with
    another file that happens to share a basename.
    """
    file_path = Path(file_path)

    if file_path.is_absolute():
        file_path = file_path.relative_to(file_path.anchor)

    return file_path
