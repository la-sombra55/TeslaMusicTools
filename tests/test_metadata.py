from pathlib import Path

from tesla_music import metadata


class FakeAudio:
    def __init__(self, tags):
        self._tags = tags

    def get(self, key, default):
        return self._tags.get(key, default)


def test_read_metadata_populates_song_from_tags(monkeypatch):
    monkeypatch.setattr(
        metadata,
        "File",
        lambda path, easy=True: FakeAudio(
            {
                "artist": ["Chris Brown"],
                "albumartist": ["Chris Brown"],
                "album": ["X"],
                "title": ["Deuces"],
            }
        ),
    )

    song = metadata.read_metadata(Path("song.mp3"))

    assert song.artist == "Chris Brown"
    assert song.album_artist == "Chris Brown"
    assert song.album == "X"
    assert song.title == "Deuces"


def test_read_metadata_defaults_missing_tags_to_unknown(monkeypatch):
    monkeypatch.setattr(metadata, "File", lambda path, easy=True: FakeAudio({}))

    song = metadata.read_metadata(Path("song.mp3"))

    assert song.artist == "Unknown"
    assert song.album == "Unknown"


def test_read_metadata_returns_song_with_defaults_when_audio_is_none(monkeypatch):
    monkeypatch.setattr(metadata, "File", lambda path, easy=True: None)

    song = metadata.read_metadata(Path("song.mp3"))

    assert song.artist == "Unknown"
    assert song.path == Path("song.mp3")


class FakeID3Frame:
    def __init__(self, text):
        self.text = [text]


def test_read_metadata_falls_back_to_raw_id3_frames_for_wav_files(monkeypatch):
    monkeypatch.setattr(
        metadata,
        "File",
        lambda path, easy=True: FakeAudio(
            {
                "TPE1": FakeID3Frame("Chris Brown"),
                "TALB": FakeID3Frame("X"),
                "TIT2": FakeID3Frame("Deuces"),
            }
        ),
    )

    song = metadata.read_metadata(Path("song.wav"))

    assert song.artist == "Chris Brown"
    assert song.album == "X"
    assert song.title == "Deuces"
    assert song.album_artist == "Unknown"


def test_read_metadata_prefers_easy_keys_over_raw_id3_frames(monkeypatch):
    monkeypatch.setattr(
        metadata,
        "File",
        lambda path, easy=True: FakeAudio(
            {
                "artist": ["Easy Artist"],
                "TPE1": FakeID3Frame("Raw Frame Artist"),
            }
        ),
    )

    song = metadata.read_metadata(Path("song.wav"))

    assert song.artist == "Easy Artist"


def test_read_metadata_returns_none_when_file_cannot_be_read(monkeypatch):
    def raise_error(path, easy=True):
        raise Exception("corrupt file")

    monkeypatch.setattr(metadata, "File", raise_error)

    assert metadata.read_metadata(Path("song.mp3")) is None
