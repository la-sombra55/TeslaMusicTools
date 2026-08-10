from pathlib import Path

from tesla_music import analyzer
from tesla_music.analyzer import analyze_artists, analyze_formats


def test_analyze_artists_reports_progress(make_song, monkeypatch):
    songs_by_path = {
        "a.mp3": make_song("a.mp3", artist="Chris Brown"),
        "b.mp3": make_song("b.mp3", artist="Beyoncé"),
    }
    monkeypatch.setattr(analyzer, "read_metadata", lambda path: songs_by_path[str(path)])

    progress_calls = []

    analyze_artists(
        [Path("a.mp3"), Path("b.mp3")],
        on_progress=lambda done, total: progress_calls.append((done, total)),
    )

    assert progress_calls == [(1, 2), (2, 2)]


def test_analyze_artists_reports_progress_even_for_unreadable_files(monkeypatch):
    monkeypatch.setattr(analyzer, "read_metadata", lambda path: None)

    progress_calls = []

    analyze_artists(
        [Path("a.mp3")], on_progress=lambda done, total: progress_calls.append((done, total))
    )

    assert progress_calls == [(1, 1)]


def test_analyze_formats_counts_songs_by_extension(make_song):
    artist_songs = {
        "Chris Brown": [make_song("a.mp3", title="A"), make_song("b.mp3", title="B")],
        "Jay-Z & Kanye West": [make_song("c.m4a", title="C")],
    }

    formats, format_songs = analyze_formats(artist_songs)

    assert formats == {"mp3": 2, "m4a": 1}
    assert [s.title for s in format_songs["mp3"]] == ["A", "B"]
    assert [s.title for s in format_songs["m4a"]] == ["C"]


def test_analyze_formats_lowercases_extension(make_song):
    artist_songs = {"Chris Brown": [make_song("a.MP3")]}

    formats, _ = analyze_formats(artist_songs)

    assert formats == {"mp3": 1}


def test_analyze_formats_handles_empty_library():
    formats, format_songs = analyze_formats({})

    assert formats == {}
    assert format_songs == {}
