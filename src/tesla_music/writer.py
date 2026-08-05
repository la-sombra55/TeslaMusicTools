from pathlib import Path

from mutagen import File


def update_artist(file_path, new_artist):
    file_path = Path(file_path)

    suffix = file_path.suffix.lower()

    if suffix == ".mp3":
        audio = File(file_path, easy=True)

        if audio is None:
            raise ValueError(f"Could not read {file_path.name}")

        audio["artist"] = [new_artist]

    elif suffix == ".m4a":
        audio = File(file_path)

        if audio is None:
            raise ValueError(f"Could not read {file_path.name}")

        audio["\xa9ART"] = [new_artist]

    else:
        raise ValueError(
            f"Unsupported file type: {suffix}"
        )

    audio.save()

    return True