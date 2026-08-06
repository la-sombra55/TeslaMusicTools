import re

from tesla_music.backup import create_backup, list_backup_sessions, new_backup_root


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
