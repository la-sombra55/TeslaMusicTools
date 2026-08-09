from pathlib import Path

from tesla_music.paths import mirrored_path


def test_mirrored_path_leaves_relative_paths_unchanged():
    assert mirrored_path("data/input/song.mp3") == Path("data/input/song.mp3")


def test_mirrored_path_strips_the_anchor_from_absolute_paths():
    assert mirrored_path("/Users/bb/Music/song.mp3") == Path("Users/bb/Music/song.mp3")
