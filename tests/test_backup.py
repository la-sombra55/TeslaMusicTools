import re

from tesla_music.backup import (
    count_backup_files,
    create_backup,
    get_backup_library_path,
    list_backup_sessions,
    new_backup_root,
    record_backup_library_path,
)


def test_new_backup_root_uses_a_fresh_timestamp_under_data_backups():
    root = new_backup_root()

    assert root.parent.name == "backups"
    assert re.fullmatch(r"\d{8}_\d{6}", root.name)


def test_create_backup_mirrors_the_original_relative_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    source = "data/input/Chris Brown/Fortune/12 Party Hard.mp3"
    (tmp_path / "data/input/Chris Brown/Fortune").mkdir(parents=True)
    (tmp_path / source).write_bytes(b"fake audio bytes")

    destination = create_backup(source, tmp_path / "data/backups/20260806_120000")

    assert destination == tmp_path / "data/backups/20260806_120000" / source
    assert destination.read_bytes() == b"fake audio bytes"


def test_create_backup_preserves_original_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    source = tmp_path / "song.mp3"
    source.write_bytes(b"original")

    create_backup(source, tmp_path / "backup")

    assert source.read_bytes() == b"original"


def test_create_backup_avoids_collisions_for_same_filename_in_different_folders(tmp_path):
    (tmp_path / "Chris Brown/Fortune").mkdir(parents=True)
    (tmp_path / "Jay-Z/Watch The Throne").mkdir(parents=True)
    (tmp_path / "Chris Brown/Fortune/01 Intro.mp3").write_bytes(b"chris brown intro")
    (tmp_path / "Jay-Z/Watch The Throne/01 Intro.mp3").write_bytes(b"jay z intro")

    backup_root = tmp_path / "backups" / "session"

    destination_a = create_backup(tmp_path / "Chris Brown/Fortune/01 Intro.mp3", backup_root)
    destination_b = create_backup(tmp_path / "Jay-Z/Watch The Throne/01 Intro.mp3", backup_root)

    assert destination_a != destination_b
    assert destination_a.read_bytes() == b"chris brown intro"
    assert destination_b.read_bytes() == b"jay z intro"


def test_create_backup_defaults_to_a_fresh_backup_root_when_none_given(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    (tmp_path / "song.mp3").write_bytes(b"audio")

    destination = create_backup("song.mp3")

    assert destination.parent.parent.name == "backups"
    assert re.fullmatch(r"\d{8}_\d{6}", destination.parent.name)


def test_list_backup_sessions_returns_most_recent_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    (tmp_path / "data/backups/20260101_010101").mkdir(parents=True)
    (tmp_path / "data/backups/20260806_120000").mkdir(parents=True)
    (tmp_path / "data/backups/20260305_090000").mkdir(parents=True)

    assert list_backup_sessions() == [
        "20260806_120000",
        "20260305_090000",
        "20260101_010101",
    ]


def test_list_backup_sessions_returns_empty_list_when_no_backups_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert list_backup_sessions() == []


def test_count_backup_files_counts_files_recursively(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    session_root = tmp_path / "data/backups/20260806_120000"
    (session_root / "Artist" / "Album").mkdir(parents=True)
    (session_root / "top.mp3").write_bytes(b"")
    (session_root / "Artist" / "Album" / "song.mp3").write_bytes(b"")

    assert count_backup_files("20260806_120000") == 2


def test_count_backup_files_returns_zero_for_missing_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert count_backup_files("does_not_exist") == 0


def test_count_backup_files_excludes_the_library_path_marker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    session_root = tmp_path / "data/backups/20260806_120000"
    session_root.mkdir(parents=True)
    (session_root / "top.mp3").write_bytes(b"")
    record_backup_library_path(session_root, tmp_path / "input")

    assert count_backup_files("20260806_120000") == 1


def test_record_and_get_backup_library_path_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    library_path = tmp_path / "MyLibrary"
    library_path.mkdir()

    session_root = tmp_path / "data/backups/20260806_120000"
    record_backup_library_path(session_root, library_path)

    assert get_backup_library_path("20260806_120000") == str(library_path.resolve())


def test_record_backup_library_path_resolves_relative_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/input").mkdir(parents=True)

    session_root = tmp_path / "data/backups/20260806_120000"
    record_backup_library_path(session_root, "data/input")

    assert get_backup_library_path("20260806_120000") == str((tmp_path / "data/input").resolve())


def test_get_backup_library_path_returns_none_when_never_recorded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    (tmp_path / "data/backups/20260806_120000").mkdir(parents=True)

    assert get_backup_library_path("20260806_120000") is None
