from pathlib import Path

from mutagen import File


MP3_EASY_KEYS = {
    "artist": "artist",
    "title": "title",
    "album": "album",
    "album_artist": "albumartist",
}

MP4_ATOMS = {
    "artist": "\xa9ART",
    "title": "\xa9nam",
    "album": "\xa9alb",
    "album_artist": "aART",
}


def update_tags(file_path, tags):
    file_path = Path(file_path)

    suffix = file_path.suffix.lower()

    if suffix == ".mp3":
        audio = File(file_path, easy=True)

        if audio is None:
            raise ValueError(f"Could not read {file_path.name}")

        for field, value in tags.items():
            audio[MP3_EASY_KEYS[field]] = [value]

    elif suffix == ".m4a":
        audio = File(file_path)

        if audio is None:
            raise ValueError(f"Could not read {file_path.name}")

        for field, value in tags.items():
            audio[MP4_ATOMS[field]] = [value]

    else:
        raise ValueError(
            f"Unsupported file type: {suffix}"
        )

    audio.save()

    return True


def update_artist(file_path, new_artist):
    return update_tags(file_path, {"artist": new_artist})
