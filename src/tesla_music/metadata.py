from pathlib import Path

from mutagen import File

from tesla_music.models import Song

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

    return song


def _read_bitrate_kbps(audio):
    info = getattr(audio, "info", None)
    bitrate_bps = getattr(info, "bitrate", 0) if info is not None else 0

    return (bitrate_bps or 0) // 1000