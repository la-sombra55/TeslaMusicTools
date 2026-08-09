from pathlib import Path

from tesla_music import drm_files
from tesla_music.drm_files import (
    apply_drm_moves,
    build_drm_plan,
    find_drm_songs,
    print_drm_report,
)


# --- find_drm_songs ---


def test_find_drm_songs_scans_only_drm_extensions(monkeypatch):
    captured = {}

    def fake_scan_library(library_path, extensions):
        captured["library_path"] = library_path
        captured["extensions"] = extensions
        return [Path("a.m4p")]

    monkeypatch.setattr(drm_files, "scan_library", fake_scan_library)
    monkeypatch.setattr(drm_files, "read_metadata", lambda path: None)

    find_drm_songs("data/input")

    assert captured["library_path"] == "data/input"
    assert captured["extensions"] == {".m4p"}


def test_find_drm_songs_returns_readable_songs(make_song, monkeypatch):
    monkeypatch.setattr(drm_files, "scan_library", lambda library_path, extensions: [Path("a.m4p")])
    monkeypatch.setattr(
        drm_files, "read_metadata", lambda path: make_song(path, artist="2Pac", title="All About U")
    )

    songs = find_drm_songs()

    assert len(songs) == 1
    assert songs[0].artist == "2Pac"


def test_find_drm_songs_skips_unreadable_files(monkeypatch):
    monkeypatch.setattr(drm_files, "scan_library", lambda library_path, extensions: [Path("a.m4p")])
    monkeypatch.setattr(drm_files, "read_metadata", lambda path: None)

    assert find_drm_songs() == []


# --- build_drm_plan ---


def test_build_drm_plan_mirrors_original_path(make_song):
    songs = [make_song("data/input/2Pac/1-02 All About U.m4p", artist="2Pac", title="All About U")]

    plan = build_drm_plan(songs, destination_folder="data/output/drm_review")

    assert plan["total_files"] == 1
    change = plan["changes"][0]
    assert change["source"] == "data/input/2Pac/1-02 All About U.m4p"
    assert change["destination"] == "data/output/drm_review/data/input/2Pac/1-02 All About U.m4p"
    assert change["artist"] == "2Pac"
    assert change["title"] == "All About U"


def test_build_drm_plan_handles_no_songs():
    assert build_drm_plan([]) == {"total_files": 0, "changes": []}


# --- apply_drm_moves ---


def test_apply_drm_moves_dry_run_does_not_touch_files(tmp_path):
    source = tmp_path / "song.m4p"
    source.write_bytes(b"drm audio")

    plan = {
        "total_files": 1,
        "changes": [
            {
                "source": str(source),
                "destination": str(tmp_path / "review" / "song.m4p"),
                "artist": "2Pac",
                "title": "All About U",
            }
        ],
    }

    results = apply_drm_moves(plan, dry_run=True)

    assert results[0]["status"] == "dry_run"
    assert source.exists()
    assert not (tmp_path / "review").exists()


def test_apply_drm_moves_moves_file_and_removes_original(tmp_path):
    source = tmp_path / "song.m4p"
    source.write_bytes(b"drm audio bytes")
    destination = tmp_path / "review" / "nested" / "song.m4p"

    plan = {
        "total_files": 1,
        "changes": [
            {
                "source": str(source),
                "destination": str(destination),
                "artist": "2Pac",
                "title": "All About U",
            }
        ],
    }

    results = apply_drm_moves(plan, dry_run=False)

    assert results[0]["status"] == "moved"
    assert destination.read_bytes() == b"drm audio bytes"
    assert not source.exists()


def test_apply_drm_moves_records_failure_for_missing_source(tmp_path):
    plan = {
        "total_files": 1,
        "changes": [
            {
                "source": str(tmp_path / "does_not_exist.m4p"),
                "destination": str(tmp_path / "review" / "x.m4p"),
                "artist": "2Pac",
                "title": "All About U",
            }
        ],
    }

    results = apply_drm_moves(plan, dry_run=False)

    assert results[0]["status"] == "failed"
    assert "error" in results[0]


def test_print_drm_report_summarizes_status_counts(capsys):
    results = [
        {"source": "a.m4p", "destination": "review/a.m4p", "status": "moved"},
        {"source": "b.m4p", "destination": "review/b.m4p", "status": "dry_run"},
        {"source": "c.m4p", "destination": "review/c.m4p", "status": "failed", "error": "boom"},
    ]

    print_drm_report(results)

    output = capsys.readouterr().out
    assert "Total files processed: 3" in output
    assert "Moved: 1" in output
    assert "Dry runs: 1" in output
    assert "Failed: 1" in output
