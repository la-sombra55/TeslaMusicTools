from datetime import datetime, timedelta

from tesla_music import import_history
from tesla_music.import_history import (
    find_songs_from_sessions_between,
    list_import_sessions,
    record_import_session,
)


def test_record_import_session_stores_songs_and_timestamp(tmp_path, monkeypatch):
    monkeypatch.setattr(import_history, "IMPORT_HISTORY_FILE", tmp_path / "history.json")

    now = datetime.now()
    record_import_session(["a.mp3", "b.mp3"], timestamp=now)

    sessions = list_import_sessions()

    assert len(sessions) == 1
    assert sessions[0]["songs"] == ["a.mp3", "b.mp3"]
    assert sessions[0]["timestamp"] == now.isoformat()


def test_list_import_sessions_returns_empty_when_none_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(import_history, "IMPORT_HISTORY_FILE", tmp_path / "history.json")

    assert list_import_sessions() == []


def test_record_import_session_appends_rather_than_overwrites(tmp_path, monkeypatch):
    monkeypatch.setattr(import_history, "IMPORT_HISTORY_FILE", tmp_path / "history.json")

    record_import_session(["a.mp3"], timestamp=datetime.now())
    record_import_session(["b.mp3"], timestamp=datetime.now())

    assert len(list_import_sessions()) == 2


def test_find_songs_from_sessions_between_includes_a_session_in_range(tmp_path, monkeypatch):
    monkeypatch.setattr(import_history, "IMPORT_HISTORY_FILE", tmp_path / "history.json")

    now = datetime.now()
    record_import_session(["a.mp3", "b.mp3"], timestamp=now)

    paths = find_songs_from_sessions_between(now - timedelta(hours=1), now + timedelta(hours=1))

    assert paths == {"a.mp3", "b.mp3"}


def test_find_songs_from_sessions_between_excludes_a_session_outside_range(tmp_path, monkeypatch):
    monkeypatch.setattr(import_history, "IMPORT_HISTORY_FILE", tmp_path / "history.json")

    old_timestamp = datetime.now() - timedelta(days=10)
    record_import_session(["a.mp3"], timestamp=old_timestamp)

    now = datetime.now()
    paths = find_songs_from_sessions_between(now - timedelta(hours=1), now + timedelta(hours=1))

    assert paths == set()


def test_find_songs_from_sessions_between_unions_multiple_matching_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(import_history, "IMPORT_HISTORY_FILE", tmp_path / "history.json")

    now = datetime.now()
    record_import_session(["a.mp3"], timestamp=now)
    record_import_session(["b.mp3"], timestamp=now)

    paths = find_songs_from_sessions_between(now - timedelta(hours=1), now + timedelta(hours=1))

    assert paths == {"a.mp3", "b.mp3"}


def test_find_songs_from_sessions_between_handles_no_history(tmp_path, monkeypatch):
    monkeypatch.setattr(import_history, "IMPORT_HISTORY_FILE", tmp_path / "history.json")

    now = datetime.now()

    assert find_songs_from_sessions_between(now - timedelta(hours=1), now) == set()
