from pathlib import Path

import pytest

from tesla_music.models import Song


@pytest.fixture
def make_song():
    def _make_song(path, artist="Unknown", **kwargs):
        return Song(path=Path(path), artist=artist, **kwargs)

    return _make_song
