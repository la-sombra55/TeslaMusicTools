import pytest

from tesla_music.backup import record_backup_library_path
from tesla_music.restore import apply_restore, build_restore_plan


def test_build_restore_plan_maps_backup_files_to_original_relative_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    session_root = tmp_path / "data/backups/20260806_120000"
    original_dir = session_root / "data/input/Chris Brown/Fortune"
    original_dir.mkdir(parents=True)
    (original_dir / "12 Party Hard.mp3").write_bytes(b"backed up bytes")

    plan = build_restore_plan("20260806_120000")

    assert plan["backup_session"] == "20260806_120000"
    assert plan["total_files"] == 1
    assert plan["changes"][0]["original"] == "data/input/Chris Brown/Fortune/12 Party Hard.mp3"


def test_build_restore_plan_excludes_the_library_path_marker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    session_root = tmp_path / "data/backups/20260806_120000"
    original_dir = session_root / "data/input/Chris Brown/Fortune"
    original_dir.mkdir(parents=True)
    (original_dir / "12 Party Hard.mp3").write_bytes(b"backed up bytes")
    record_backup_library_path(session_root, tmp_path / "data/input")

    plan = build_restore_plan("20260806_120000")

    assert plan["total_files"] == 1
    assert plan["changes"][0]["original"] == "data/input/Chris Brown/Fortune/12 Party Hard.mp3"


def test_build_restore_plan_raises_for_unknown_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="No backup session found"):
        build_restore_plan("does_not_exist")


def test_apply_restore_dry_run_does_not_touch_files(tmp_path):
    backup_file = tmp_path / "backup.mp3"
    backup_file.write_bytes(b"backup bytes")
    original = tmp_path / "restored.mp3"

    plan = {
        "backup_session": "x",
        "total_files": 1,
        "changes": [{"backup": str(backup_file), "original": str(original)}],
    }

    results = apply_restore(plan, dry_run=True)

    assert results[0]["status"] == "dry_run"
    assert not original.exists()


def test_apply_restore_copies_backup_back_to_original_location(tmp_path):
    backup_file = tmp_path / "backup.mp3"
    backup_file.write_bytes(b"backup bytes")
    original = tmp_path / "nested" / "restored.mp3"

    plan = {
        "backup_session": "x",
        "total_files": 1,
        "changes": [{"backup": str(backup_file), "original": str(original)}],
    }

    results = apply_restore(plan, dry_run=False)

    assert results[0]["status"] == "restored"
    assert original.read_bytes() == b"backup bytes"


def test_apply_restore_records_failure_for_missing_backup_file(tmp_path):
    plan = {
        "backup_session": "x",
        "total_files": 1,
        "changes": [
            {
                "backup": str(tmp_path / "does_not_exist.mp3"),
                "original": str(tmp_path / "restored.mp3"),
            }
        ],
    }

    results = apply_restore(plan, dry_run=False)

    assert results[0]["status"] == "failed"
    assert "error" in results[0]
