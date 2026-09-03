from pathlib import Path

import pytest

from tesla_music import writer


class FakeAudio:
    def __init__(self):
        self.tags = {}
        self.saved = False

    def __setitem__(self, key, value):
        self.tags[key] = value

    def save(self):
        self.saved = True


class FakeWavTags:
    def __init__(self):
        self.frames = {}

    def add(self, frame):
        self.frames[type(frame).__name__] = frame


class FakeWaveAudio:
    def __init__(self, tags=None):
        self.tags = tags
        self.saved = False

    def add_tags(self):
        self.tags = FakeWavTags()

    def save(self):
        self.saved = True


def test_update_artist_sets_id3_artist_tag_for_mp3(monkeypatch):
    fake_audio = FakeAudio()
    monkeypatch.setattr(writer, "File", lambda path, easy=False: fake_audio)

    result = writer.update_artist(Path("song.mp3"), "Chris Brown")

    assert result is True
    assert fake_audio.tags["artist"] == ["Chris Brown"]
    assert fake_audio.saved is True


def test_update_artist_sets_mp4_artist_atom_for_m4a(monkeypatch):
    fake_audio = FakeAudio()
    monkeypatch.setattr(writer, "File", lambda path, easy=False: fake_audio)

    writer.update_artist(Path("song.m4a"), "Jay-Z & Kanye West")

    assert fake_audio.tags["\xa9ART"] == ["Jay-Z & Kanye West"]
    assert fake_audio.saved is True


def test_update_artist_raises_for_unsupported_extension(monkeypatch):
    monkeypatch.setattr(writer, "File", lambda path, easy=False: FakeAudio())

    with pytest.raises(ValueError, match="Unsupported file type"):
        writer.update_artist(Path("song.flac"), "Chris Brown")


@pytest.mark.parametrize("suffix", [".mp3", ".m4a"])
def test_update_artist_raises_when_file_cannot_be_read(monkeypatch, suffix):
    monkeypatch.setattr(writer, "File", lambda path, easy=False: None)

    with pytest.raises(ValueError, match="Could not read"):
        writer.update_artist(Path(f"song{suffix}"), "Chris Brown")


def test_update_tags_sets_artist_and_title_together_for_mp3(monkeypatch):
    fake_audio = FakeAudio()
    monkeypatch.setattr(writer, "File", lambda path, easy=False: fake_audio)

    writer.update_tags(
        Path("song.mp3"),
        {"artist": "Maroon 5", "title": "Girls Like You (feat. Cardi B)"},
    )

    assert fake_audio.tags["artist"] == ["Maroon 5"]
    assert fake_audio.tags["title"] == ["Girls Like You (feat. Cardi B)"]
    assert fake_audio.saved is True


def test_update_tags_sets_artist_and_title_together_for_m4a(monkeypatch):
    fake_audio = FakeAudio()
    monkeypatch.setattr(writer, "File", lambda path, easy=False: fake_audio)

    writer.update_tags(
        Path("song.m4a"),
        {"artist": "Maroon 5", "title": "Girls Like You (feat. Cardi B)"},
    )

    assert fake_audio.tags["\xa9ART"] == ["Maroon 5"]
    assert fake_audio.tags["\xa9nam"] == ["Girls Like You (feat. Cardi B)"]


def test_update_tags_sets_id3_frames_for_wav(monkeypatch):
    fake_audio = FakeWaveAudio(tags=FakeWavTags())
    monkeypatch.setattr(writer, "WAVE", lambda path: fake_audio)

    writer.update_tags(Path("song.wav"), {"artist": "Chris Brown", "title": "Deuces"})

    assert fake_audio.tags.frames["TPE1"].text == ["Chris Brown"]
    assert fake_audio.tags.frames["TIT2"].text == ["Deuces"]
    assert fake_audio.saved is True


def test_update_tags_creates_tags_for_wav_when_missing(monkeypatch):
    fake_audio = FakeWaveAudio(tags=None)
    monkeypatch.setattr(writer, "WAVE", lambda path: fake_audio)

    writer.update_tags(Path("song.wav"), {"artist": "Chris Brown"})

    assert fake_audio.tags is not None
    assert fake_audio.tags.frames["TPE1"].text == ["Chris Brown"]
    assert fake_audio.saved is True


def test_update_tags_sets_genre_for_mp3(monkeypatch):
    fake_audio = FakeAudio()
    monkeypatch.setattr(writer, "File", lambda path, easy=False: fake_audio)

    writer.update_tags(Path("song.mp3"), {"genre": "Hip-Hop"})

    assert fake_audio.tags["genre"] == ["Hip-Hop"]
    assert fake_audio.saved is True


def test_update_tags_sets_genre_atom_for_m4a(monkeypatch):
    fake_audio = FakeAudio()
    monkeypatch.setattr(writer, "File", lambda path, easy=False: fake_audio)

    writer.update_tags(Path("song.m4a"), {"genre": "Hip-Hop"})

    assert fake_audio.tags["\xa9gen"] == ["Hip-Hop"]
    assert fake_audio.saved is True


def test_update_tags_sets_genre_id3_frame_for_wav(monkeypatch):
    fake_audio = FakeWaveAudio(tags=FakeWavTags())
    monkeypatch.setattr(writer, "WAVE", lambda path: fake_audio)

    writer.update_tags(Path("song.wav"), {"genre": "Hip-Hop"})

    assert fake_audio.tags.frames["TCON"].text == ["Hip-Hop"]
    assert fake_audio.saved is True
