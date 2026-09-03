import re
from pathlib import Path

from mutagen import File

from tesla_music.models import Song

# Last-resort fallback for files with no metadata anywhere -- strips a
# leading track number like "10 " or "10. " off the filename so at least
# the title is a real, distinguishing value instead of every untagged file
# colliding on the shared "Unknown" placeholder (which breaks anything that
# groups songs by title, like artwork lookup and duplicate detection).
FILENAME_TRACK_NUMBER_PATTERN = re.compile(r"^\d+[\s._-]+")

# WAV files are tagged with raw ID3 frames under the hood, and unlike MP3,
# mutagen's easy=True mode doesn't map them to simple keys like "artist" --
# so those keys come back empty and every WAV field falls back to "Unknown"
# unless we also check the raw frame IDs.
ID3_FRAME_KEYS = {
    "artist": "TPE1",
    "albumartist": "TPE2",
    "album": "TALB",
    "title": "TIT2",
    "genre": "TCON",
    "grouping": "TIT1",
}


def _read_tag(audio, easy_key, default):
    value = audio.get(easy_key, None)

    if value:
        return value[0]

    frame = audio.get(ID3_FRAME_KEYS[easy_key], None)

    if frame is not None:
        return str(frame.text[0])

    return default


def read_metadata(song_path: Path):
    song = Song(path=song_path)

    try:
        audio = File(song_path, easy=True)
    except Exception as error:
        print(f"Could not read {song_path.name}: {error}")
        return None

    if audio is None:
        return song

    song.artist = _read_tag(audio, "artist", "Unknown")
    song.album_artist = _read_tag(audio, "albumartist", "Unknown")
    song.album = _read_tag(audio, "album", "Unknown")
    song.title = _read_tag(audio, "title", "Unknown")
    song.genre = _read_tag(audio, "genre", "Unknown")
    song.grouping = _read_tag(audio, "grouping", "")
    song.bitrate = _read_bitrate_kbps(audio)

    if song.title == "Unknown":
        title_from_filename = _title_from_filename(song_path)

        if title_from_filename:
            song.title = title_from_filename

    return song


def _title_from_filename(song_path):
    title = FILENAME_TRACK_NUMBER_PATTERN.sub("", song_path.stem).strip()

    return title or None


def _read_bitrate_kbps(audio):
    info = getattr(audio, "info", None)
    bitrate_bps = getattr(info, "bitrate", 0) if info is not None else 0

    return (bitrate_bps or 0) // 1000