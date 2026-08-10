from pathlib import Path

from tesla_music import duplicates
from tesla_music.duplicates import (
    apply_duplicate_moves,
    build_duplicate_plan,
    find_duplicate_songs,
    print_duplicate_report,
)


def _durations(monkeypatch, mapping):
    def fake_get_duration(path):
        return mapping.get(str(path))

    monkeypatch.setattr(duplicates, "_get_duration", fake_get_duration)


# --- find_duplicate_songs ---


def test_finds_same_title_close_duration_as_duplicates(make_song, monkeypatch):
    songs = [
        make_song("a.m4a", title="Skandalouz"),
        make_song("b.m4a", title="Skandalouz"),
    ]
    _durations(monkeypatch, {"a.m4a": 248.8, "b.m4a": 248.8})

    groups = find_duplicate_songs({"2Pac": songs})

    assert len(groups) == 1
    assert groups[0]["artist"] == "2Pac"
    assert groups[0]["title"] == "Skandalouz"
    assert {s.path.name for s in groups[0]["songs"]} == {"a.m4a", "b.m4a"}


def test_does_not_group_same_title_when_duration_differs_a_lot(make_song, monkeypatch):
    songs = [
        make_song("a.m4a", title="Intro"),
        make_song("b.m4a", title="Intro"),
    ]
    _durations(monkeypatch, {"a.m4a": 10.0, "b.m4a": 240.0})

    assert find_duplicate_songs({"2Pac": songs}) == []


def test_does_not_group_across_different_artists(make_song, monkeypatch):
    songs_a = [make_song("a.m4a", title="Intro")]
    songs_b = [make_song("b.m4a", title="Intro")]
    _durations(monkeypatch, {"a.m4a": 15.0, "b.m4a": 15.0})

    groups = find_duplicate_songs({"Artist A": songs_a, "Artist B": songs_b})

    assert groups == []


def test_does_not_group_different_titles(make_song, monkeypatch):
    songs = [
        make_song("a.m4a", title="Skandalouz"),
        make_song("b.m4a", title="All About U"),
    ]
    _durations(monkeypatch, {"a.m4a": 248.8, "b.m4a": 248.8})

    assert find_duplicate_songs({"2Pac": songs}) == []


def test_groups_titles_that_differ_only_by_case(make_song, monkeypatch):
    songs = [
        make_song("a.m4a", title="Skandalouz"),
        make_song("b.m4a", title="SKANDALOUZ"),
    ]
    _durations(monkeypatch, {"a.m4a": 248.8, "b.m4a": 249.5})

    groups = find_duplicate_songs({"2Pac": songs})

    assert len(groups) == 1


def test_excludes_songs_with_unreadable_duration(make_song, monkeypatch):
    songs = [
        make_song("a.m4a", title="Skandalouz"),
        make_song("b.m4a", title="Skandalouz"),
    ]
    _durations(monkeypatch, {"a.m4a": 248.8, "b.m4a": None})

    assert find_duplicate_songs({"2Pac": songs}) == []


def test_groups_three_or_more_duplicates_together(make_song, monkeypatch):
    songs = [
        make_song("a.m4a", title="Ambitionz Az a Ridah"),
        make_song("b.m4a", title="Ambitionz Az a Ridah"),
        make_song("c.m4a", title="Ambitionz Az a Ridah"),
    ]
    _durations(monkeypatch, {"a.m4a": 278.5, "b.m4a": 278.5, "c.m4a": 279.0})

    groups = find_duplicate_songs({"2Pac": songs})

    assert len(groups) == 1
    assert len(groups[0]["songs"]) == 3


def test_returns_empty_for_no_songs():
    assert find_duplicate_songs({}) == []


# --- build_duplicate_plan ---


def test_build_duplicate_plan_keeps_the_non_drm_non_suffixed_file(make_song):
    group = {
        "artist": "2Pac",
        "title": "Skandalouz",
        "songs": [
            make_song(
                "data/input/2Pac/All Eyez On Me (Remastered)/1-03 Skandalouz 1.m4a",
                title="Skandalouz",
            ),
            make_song(
                "data/input/2Pac/All Eyez On Me (Remastered)/1-03 Skandalouz.m4a",
                title="Skandalouz",
            ),
        ],
    }

    plan = build_duplicate_plan([group], destination_folder="data/output/duplicates_review")

    assert plan["total_files"] == 1
    change = plan["changes"][0]
    assert change["source"].endswith("Skandalouz 1.m4a")
    assert change["keep"].endswith("Skandalouz.m4a")
    assert change["destination"] == (
        "data/output/duplicates_review/data/input/2Pac/"
        "All Eyez On Me (Remastered)/1-03 Skandalouz 1.m4a"
    )


def test_build_duplicate_plan_prefers_non_drm_file_over_m4p(make_song):
    group = {
        "artist": "2Pac",
        "title": "All About U",
        "songs": [
            make_song("data/input/2Pac/1-02 All About U.m4p", title="All About U"),
            make_song("data/input/2Pac/1-02 All About U.m4a", title="All About U"),
        ],
    }

    plan = build_duplicate_plan([group])

    assert plan["changes"][0]["source"].endswith(".m4p")
    assert plan["changes"][0]["keep"].endswith(".m4a")


def test_build_duplicate_plan_handles_no_groups():
    assert build_duplicate_plan([]) == {
        "total_files": 0,
        "destination_folder": "data/output/duplicates_review",
        "changes": [],
    }


# --- apply_duplicate_moves ---


def test_apply_duplicate_moves_dry_run_does_not_touch_files(tmp_path):
    source = tmp_path / "song.m4a"
    source.write_bytes(b"audio")

    plan = {
        "total_files": 1,
        "changes": [
            {
                "source": str(source),
                "destination": str(tmp_path / "review" / "song.m4a"),
                "keep": "keep.m4a",
                "artist": "2Pac",
                "title": "Skandalouz",
            }
        ],
    }

    results = apply_duplicate_moves(plan, dry_run=True)

    assert results[0]["status"] == "dry_run"
    assert source.exists()
    assert not (tmp_path / "review").exists()


def test_apply_duplicate_moves_moves_file_and_removes_original(tmp_path):
    source = tmp_path / "song.m4a"
    source.write_bytes(b"audio bytes")
    destination = tmp_path / "review" / "nested" / "song.m4a"

    plan = {
        "total_files": 1,
        "changes": [
            {
                "source": str(source),
                "destination": str(destination),
                "keep": "keep.m4a",
                "artist": "2Pac",
                "title": "Skandalouz",
            }
        ],
    }

    results = apply_duplicate_moves(plan, dry_run=False)

    assert results[0]["status"] == "moved"
    assert destination.read_bytes() == b"audio bytes"
    assert not source.exists()


def test_apply_duplicate_moves_records_failure_for_missing_source(tmp_path):
    plan = {
        "total_files": 1,
        "changes": [
            {
                "source": str(tmp_path / "does_not_exist.m4a"),
                "destination": str(tmp_path / "review" / "x.m4a"),
                "keep": "keep.m4a",
                "artist": "2Pac",
                "title": "Skandalouz",
            }
        ],
    }

    results = apply_duplicate_moves(plan, dry_run=False)

    assert results[0]["status"] == "failed"
    assert "error" in results[0]


def test_print_duplicate_report_summarizes_status_counts(capsys):
    results = [
        {"source": "a.m4a", "destination": "review/a.m4a", "status": "moved"},
        {"source": "b.m4a", "destination": "review/b.m4a", "status": "dry_run"},
        {"source": "c.m4a", "destination": "review/c.m4a", "status": "failed", "error": "boom"},
    ]

    print_duplicate_report(results)

    output = capsys.readouterr().out
    assert "Total files processed: 3" in output
    assert "Moved: 1" in output
    assert "Dry runs: 1" in output
    assert "Failed: 1" in output
