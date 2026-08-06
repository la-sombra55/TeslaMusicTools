import re

from tesla_music.backup import create_backup


def test_create_backup_copies_file_into_timestamped_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    source = tmp_path / "song.mp3"
    source.write_bytes(b"fake audio bytes")

    destination = create_backup(source)

    assert destination.read_bytes() == b"fake audio bytes"
    assert destination.parent.parent.name == "backups"
    assert re.fullmatch(r"\d{8}_\d{6}", destination.parent.name)


def test_create_backup_preserves_original_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    source = tmp_path / "song.mp3"
    source.write_bytes(b"original")

    create_backup(source)

    assert source.read_bytes() == b"original"
