from pathlib import Path

from tesla_music import apply


def _plan(changes):
    return {"total_changes": len(changes), "changes": changes}


def test_dry_run_marks_every_change_as_dry_run_without_touching_files(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("dry_run must not touch the filesystem")

    monkeypatch.setattr(apply, "create_backup", fail_if_called)
    monkeypatch.setattr(apply, "update_tags", fail_if_called)

    plan = _plan(
        [{"file": "a.mp3", "current_artist": "chris brown", "new_artist": "Chris Brown"}]
    )

    results = apply.apply_changes(plan, dry_run=True)

    assert results[0]["status"] == "dry_run"


def test_successful_apply_backs_up_then_updates_and_records_backup_path(monkeypatch):
    monkeypatch.setattr(
        apply, "create_backup", lambda file_path, backup_root: Path("data/backups/x/a.mp3")
    )
    monkeypatch.setattr(apply, "update_tags", lambda file_path, tags: True)

    plan = _plan(
        [{"file": "a.mp3", "current_artist": "chris brown", "new_artist": "Chris Brown"}]
    )

    results = apply.apply_changes(plan, dry_run=False)

    assert results[0]["status"] == "updated"
    assert results[0]["backup"] == "data/backups/x/a.mp3"


def test_successful_apply_only_passes_fields_that_changed(monkeypatch):
    monkeypatch.setattr(
        apply, "create_backup", lambda file_path, backup_root: Path("data/backups/x/a.mp3")
    )

    captured_tags = {}

    def fake_update_tags(file_path, tags):
        captured_tags.update(tags)
        return True

    monkeypatch.setattr(apply, "update_tags", fake_update_tags)

    plan = _plan(
        [
            {
                "file": "a.mp3",
                "current_artist": "Maroon 5 feat. Cardi B",
                "new_artist": "Maroon 5",
                "current_title": "Girls Like You",
                "new_title": "Girls Like You (feat. Cardi B)",
            }
        ]
    )

    apply.apply_changes(plan, dry_run=False)

    assert captured_tags == {
        "artist": "Maroon 5",
        "title": "Girls Like You (feat. Cardi B)",
    }


def test_failed_update_is_recorded_but_does_not_raise(monkeypatch):
    monkeypatch.setattr(
        apply, "create_backup", lambda file_path, backup_root: Path("data/backups/x/a.mp3")
    )

    def raise_error(file_path, tags):
        raise ValueError("Unsupported file type: .flac")

    monkeypatch.setattr(apply, "update_tags", raise_error)

    plan = _plan(
        [{"file": "a.flac", "current_artist": "chris brown", "new_artist": "Chris Brown"}]
    )

    results = apply.apply_changes(plan, dry_run=False)

    assert results[0]["status"] == "failed"
    assert "Unsupported file type" in results[0]["error"]


def test_print_apply_report_summarizes_status_counts(capsys):
    results = [
        {"file": "a.mp3", "current_artist": "x", "new_artist": "y", "status": "updated"},
        {"file": "b.mp3", "current_artist": "x", "new_artist": "y", "status": "dry_run"},
        {"file": "c.mp3", "current_artist": "x", "new_artist": "y", "status": "failed", "error": "boom"},
    ]

    apply.print_apply_report(results)

    output = capsys.readouterr().out
    assert "Total files processed: 3" in output
    assert "Successful updates: 1" in output
    assert "Dry runs: 1" in output
    assert "Failed updates: 1" in output
    assert "Artist: x → y" in output


def test_print_apply_report_shows_title_change_when_present(capsys):
    results = [
        {
            "file": "a.mp3",
            "current_artist": "Maroon 5 feat. Cardi B",
            "new_artist": "Maroon 5",
            "current_title": "Girls Like You",
            "new_title": "Girls Like You (feat. Cardi B)",
            "status": "updated",
        }
    ]

    apply.print_apply_report(results)

    output = capsys.readouterr().out
    assert "Title: Girls Like You → Girls Like You (feat. Cardi B)" in output


def test_successful_apply_writes_album_tag_when_present(monkeypatch):
    monkeypatch.setattr(
        apply, "create_backup", lambda file_path, backup_root: Path("data/backups/x/b.mp3")
    )

    captured_tags = {}

    def fake_update_tags(file_path, tags):
        captured_tags.update(tags)
        return True

    monkeypatch.setattr(apply, "update_tags", fake_update_tags)

    plan = _plan(
        [
            {
                "file": "b.mp3",
                "artist": "T.I.",
                "current_album": "The King",
                "new_album": "The KING",
            }
        ]
    )

    results = apply.apply_changes(plan, dry_run=False)

    assert captured_tags == {"album": "The KING"}
    assert results[0]["current_album"] == "The King"
    assert results[0]["new_album"] == "The KING"


def test_print_apply_report_shows_album_change_when_present(capsys):
    results = [
        {
            "file": "b.mp3",
            "current_album": "The King",
            "new_album": "The KING",
            "status": "updated",
        }
    ]

    apply.print_apply_report(results)

    output = capsys.readouterr().out
    assert "Album: The King → The KING" in output
