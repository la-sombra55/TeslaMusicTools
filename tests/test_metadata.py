import struct
from pathlib import Path

from tesla_music import metadata


def _write_aiff(path, tags=None):
    """
    Builds a minimal real AIFF file (COMM + SSND, plus arbitrary extra
    chunks) so the native-chunk fallback can be tested against actual file
    bytes rather than a mock -- it reads the file directly, bypassing the
    mutagen `File`/`easy=True` path the other tests mock.
    """
    sample_rate_bytes = bytes.fromhex("400EAC44000000000000")
    comm_data = struct.pack(">hlh", 2, 100, 16) + sample_rate_bytes
    comm_chunk = b"COMM" + struct.pack(">I", len(comm_data)) + comm_data

    tag_chunks = b""
    for chunk_id, text in (tags or {}).items():
        data = text.encode("utf-8")
        tag_chunks += chunk_id.encode("ascii") + struct.pack(">I", len(data)) + data
        if len(data) % 2 == 1:
            tag_chunks += b"\x00"

    sound_data = b"\x00" * (100 * 4)
    ssnd_data = struct.pack(">II", 0, 0) + sound_data
    ssnd_chunk = b"SSND" + struct.pack(">I", len(ssnd_data)) + ssnd_data

    form_data = b"AIFF" + comm_chunk + tag_chunks + ssnd_chunk
    Path(path).write_bytes(b"FORM" + struct.pack(">I", len(form_data)) + form_data)


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


def test_read_metadata_falls_back_to_native_aiff_chunks_when_no_id3(tmp_path):
    # Classic AIFF (predating ID3) stores title/artist in its own NAME/AUTH
    # chunks -- some CD-ripping tools still write these instead of ID3.
    path = tmp_path / "song.aiff"
    _write_aiff(path, tags={"NAME": "West Coast Smoker", "AUTH": "Anna Merritt"})

    song = metadata.read_metadata(path)

    assert song.title == "West Coast Smoker"
    assert song.artist == "Anna Merritt"
    assert song.album == "Unknown"  # no album chunk exists in the AIFF spec


def test_read_metadata_falls_back_to_filename_for_a_fully_untagged_aiff(tmp_path):
    # No ID3, no native AIFF chunks -- the only signal left is the filename
    # itself. Real-world case: CD rips with a "## Title.aiff" naming
    # convention and zero embedded metadata anywhere.
    path = tmp_path / "10 Armistice.aiff"
    _write_aiff(path)

    song = metadata.read_metadata(path)

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


def test_read_metadata_prefers_id3_over_native_aiff_chunks(tmp_path, monkeypatch):
    path = tmp_path / "song.aiff"
    _write_aiff(path, tags={"NAME": "Native Title", "AUTH": "Native Artist"})

    monkeypatch.setattr(
        metadata,
        "File",
        lambda p, easy=True: FakeAudio({"artist": ["ID3 Artist"], "title": ["ID3 Title"]}),
    )

    song = metadata.read_metadata(path)

    assert song.title == "ID3 Title"
    assert song.artist == "ID3 Artist"


def test_read_metadata_returns_none_when_file_cannot_be_read(monkeypatch):
    def raise_error(path, easy=True):
        raise Exception("corrupt file")

    monkeypatch.setattr(metadata, "File", raise_error)

    assert metadata.read_metadata(Path("song.mp3")) is None
