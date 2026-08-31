import re
from pathlib import Path

from mutagen import File
from mutagen.aiff import AIFFFile

from tesla_music.models import Song

# Last-resort fallback for files with no metadata anywhere (no tags, no
# native chunks) -- strips a leading track number like "10 " or "10. " off
# the filename so at least the title is a real, distinguishing value
# instead of every untagged file colliding on the shared "Unknown"
# placeholder (which breaks anything that groups songs by title, like
# artwork lookup and duplicate detection).
FILENAME_TRACK_NUMBER_PATTERN = re.compile(r"^\d+[\s._-]+")

AIFF_EXTENSIONS = (".aiff", ".aif")

# Classic AIFF (predating ID3) has its own native text chunks -- NAME for
# title, AUTH for artist. There's no album chunk in the AIFF spec at all.
# Plenty of CD-ripping tools still write these instead of an ID3 tag, which
# mutagen's AIFF support doesn't read at all -- so a file tagged this way
# comes back as "Unknown" from the normal path above unless we also check
# for these chunks directly.
AIFF_NATIVE_CHUNKS = {
    "title": "NAME",
    "artist": "AUTH",
}

# WAV files are tagged with raw ID3 frames under the hood, and unlike MP3,
# mutagen's easy=True mode doesn't map them to simple keys like "artist" --
# so those keys come back empty and every WAV field falls back to "Unknown"
# unless we also check the raw frame IDs.
ID3_FRAME_KEYS = {
    "artist": "TPE1",
    "albumartist": "TPE2",
    "album": "TALB",
    "title": "TIT2",
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
    song.bitrate = _read_bitrate_kbps(audio)

    if song_path.suffix.lower() in AIFF_EXTENSIONS and (
        song.title == "Unknown" or song.artist == "Unknown"
    ):
        native_tags = _read_native_aiff_tags(song_path)

        if song.title == "Unknown" and native_tags.get("title"):
            song.title = native_tags["title"]

        if song.artist == "Unknown" and native_tags.get("artist"):
            song.artist = native_tags["artist"]

    if song.title == "Unknown":
        title_from_filename = _title_from_filename(song_path)

        if title_from_filename:
            song.title = title_from_filename

    return song


def _title_from_filename(song_path):
    title = FILENAME_TRACK_NUMBER_PATTERN.sub("", song_path.stem).strip()

    return title or None


def _read_native_aiff_tags(song_path):
    try:
        with open(song_path, "rb") as file:
            iff = AIFFFile(file)

            return {
                field: iff[chunk_id].read().decode("utf-8", errors="replace").strip(" \x00")
                for field, chunk_id in AIFF_NATIVE_CHUNKS.items()
                if chunk_id in iff
            }
    except Exception:
        return {}


def _read_bitrate_kbps(audio):
    info = getattr(audio, "info", None)
    bitrate_bps = getattr(info, "bitrate", 0) if info is not None else 0

    return (bitrate_bps or 0) // 1000