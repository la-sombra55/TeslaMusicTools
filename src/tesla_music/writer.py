from pathlib import Path

from mutagen import File
from mutagen.id3 import TALB, TCON, TIT2, TPE1, TPE2
from mutagen.wave import WAVE


MP3_EASY_KEYS = {
    "artist": "artist",
    "title": "title",
    "album": "album",
    "album_artist": "albumartist",
    "genre": "genre",
}

MP4_ATOMS = {
    "artist": "\xa9ART",
    "title": "\xa9nam",
    "album": "\xa9alb",
    "album_artist": "aART",
    "genre": "\xa9gen",
}

# WAV stores tags as raw ID3 frames (same as MP3 under the hood), but
# mutagen's easy=True mode doesn't map those to simple keys the way it does
# for MP3 -- see the matching ID3_FRAME_KEYS note in metadata.py.
WAV_ID3_FRAMES = {
    "artist": TPE1,
    "title": TIT2,
    "album": TALB,
    "album_artist": TPE2,
    "genre": TCON,
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

    elif suffix == ".wav":
        audio = WAVE(file_path)

        if audio.tags is None:
            audio.add_tags()

        wav_tags = audio.tags
        assert wav_tags is not None

        for field, value in tags.items():
            frame_class = WAV_ID3_FRAMES[field]
            wav_tags.add(frame_class(encoding=3, text=[value]))

    else:
        raise ValueError(
            f"Unsupported file type: {suffix}"
        )

    audio.save()

    return True


def update_artist(file_path, new_artist):
    return update_tags(file_path, {"artist": new_artist})
