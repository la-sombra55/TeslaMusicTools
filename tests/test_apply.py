from pathlib import Path

from tesla_music import apply


def _plan(changes):
    return {"total_changes": len(changes), "changes": changes}


def test_dry_run_marks_every_change_as_dry_run_without_touching_files(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("dry_run must not touch the filesystem")

    monkeypatch.setattr(apply, "create_backup", fail_if_called)
    monkeypatch.setattr(apply, "update_artist", fail_if_called)

    plan = _plan(
        [{"file": "a.mp3", "current_artist": "chris brown", "new_artist": "Chris Brown"}]
    )

    results = apply.apply_changes(plan, dry_run=True)

    assert results[0]["status"] == "dry_run"


def test_successful_apply_backs_up_then_updates_and_records_backup_path(monkeypatch):
    monkeypatch.setattr(apply, "create_backup", lambda file_path: Path("data/backups/x/a.mp3"))
    monkeypatch.setattr(apply, "update_artist", lambda file_path, new_artist: True)

    plan = _plan(
        [{"file": "a.mp3", "current_artist": "chris brown", "new_artist": "Chris Brown"}]
    )

    results = apply.apply_changes(plan, dry_run=False)

    assert results[0]["status"] == "updated"
    assert results[0]["backup"] == "data/backups/x/a.mp3"


def test_failed_update_is_recorded_but_does_not_raise(monkeypatch):
    monkeypatch.setattr(apply, "create_backup", lambda file_path: Path("data/backups/x/a.mp3"))

    def raise_error(file_path, new_artist):
        raise ValueError("Unsupported file type: .flac")

    monkeypatch.setattr(apply, "update_artist", raise_error)

    plan = _plan(
        [{"file": "a.flac", "current_artist": "chris brown", "new_artist": "Chris Brown"}]
    )

    results = apply.apply_changes(plan, dry_run=False)

    assert results[0]["status"] == "failed"
    assert "Unsupported file type" in results[0]["error"]


def test_print_apply_report_summarizes_status_counts(capsys):
    results = [
        {"file": "a.mp3", "from": "x", "to": "y", "status": "updated"},
        {"file": "b.mp3", "from": "x", "to": "y", "status": "dry_run"},
        {"file": "c.mp3", "from": "x", "to": "y", "status": "failed", "error": "boom"},
    ]

    apply.print_apply_report(results)

    output = capsys.readouterr().out
    assert "Total files processed: 3" in output
    assert "Successful updates: 1" in output
    assert "Dry runs: 1" in output
    assert "Failed updates: 1" in output
