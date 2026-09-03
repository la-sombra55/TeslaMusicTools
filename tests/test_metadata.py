from pathlib import Path

from tesla_music import metadata


class FakeInfo:
    def __init__(self, bitrate):
        self.bitrate = bitrate


class FakeAudio:
    def __init__(self, tags, info=None):
        self._tags = tags
        self.info = info

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
                "genre": ["Hip-Hop"],
            }
        ),
    )

    song = metadata.read_metadata(Path("song.mp3"))

    assert song.artist == "Chris Brown"
    assert song.album_artist == "Chris Brown"
    assert song.album == "X"
    assert song.title == "Deuces"
    assert song.genre == "Hip-Hop"


def test_read_metadata_defaults_missing_tags_to_unknown(monkeypatch):
    monkeypatch.setattr(metadata, "File", lambda path, easy=True: FakeAudio({}))

    song = metadata.read_metadata(Path("song.mp3"))

    assert song.artist == "Unknown"
    assert song.album == "Unknown"
    assert song.genre == "Unknown"


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
                "TCON": FakeID3Frame("Hip-Hop"),
            }
        ),
    )

    song = metadata.read_metadata(Path("song.wav"))

    assert song.artist == "Chris Brown"
    assert song.album == "X"
    assert song.title == "Deuces"
    assert song.album_artist == "Unknown"
    assert song.genre == "Hip-Hop"


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


def test_read_metadata_converts_bitrate_from_bps_to_kbps(monkeypatch):
    monkeypatch.setattr(
        metadata,
        "File",
        lambda path, easy=True: FakeAudio({}, info=FakeInfo(bitrate=320000)),
    )

    song = metadata.read_metadata(Path("song.mp3"))

    assert song.bitrate == 320


def test_read_metadata_defaults_bitrate_to_zero_when_info_missing(monkeypatch):
    monkeypatch.setattr(metadata, "File", lambda path, easy=True: FakeAudio({}, info=None))

    song = metadata.read_metadata(Path("song.mp3"))

    assert song.bitrate == 0


def test_read_metadata_defaults_bitrate_to_zero_when_audio_is_none(monkeypatch):
    monkeypatch.setattr(metadata, "File", lambda path, easy=True: None)

    song = metadata.read_metadata(Path("song.mp3"))

    assert song.bitrate == 0


def test_read_metadata_falls_back_to_filename_for_a_fully_untagged_file(tmp_path, monkeypatch):
    # No tags anywhere -- the only signal left is the filename itself. Real
    # -world case: CD rips with a "## Title.ext" naming convention and zero
    # embedded metadata.
    monkeypatch.setattr(metadata, "File", lambda p, easy=True: FakeAudio({}))

    song = metadata.read_metadata(tmp_path / "10 Armistice.mp3")

    assert song.title == "Armistice"
    assert song.artist == "Unknown"  # no artist info exists anywhere to infer this from


def test_title_from_filename_strips_various_track_number_separators(tmp_path, monkeypatch):
    monkeypatch.setattr(metadata, "File", lambda p, easy=True: FakeAudio({}))

    for filename, expected_title in [
        ("10 Armistice.mp3", "Armistice"),
        ("01. Armistice.mp3", "Armistice"),
        ("01-Armistice.mp3", "Armistice"),
        ("01_Armistice.mp3", "Armistice"),
        ("Armistice.mp3", "Armistice"),  # no leading track number at all
    ]:
        song = metadata.read_metadata(tmp_path / filename)
        assert song.title == expected_title, filename


def test_read_metadata_does_not_use_filename_when_a_real_title_is_tagged(monkeypatch):
    monkeypatch.setattr(
        metadata, "File", lambda p, easy=True: FakeAudio({"title": ["Real Title"]})
    )

    song = metadata.read_metadata(Path("10 Different Filename.mp3"))

    assert song.title == "Real Title"


def test_read_metadata_returns_none_when_file_cannot_be_read(monkeypatch):
    def raise_error(path, easy=True):
        raise Exception("corrupt file")

    monkeypatch.setattr(metadata, "File", raise_error)

    assert metadata.read_metadata(Path("song.mp3")) is None
