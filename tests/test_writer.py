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
