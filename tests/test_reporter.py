from tesla_music.reporter import build_review_report, save_review_report


def _change(file, current_artist, new_artist, confidence=95, reason="Capitalization difference only"):
    return {
        "file": file,
        "current_artist": current_artist,
        "new_artist": new_artist,
        "confidence": confidence,
        "reason": reason,
    }


def test_build_review_report_groups_changes_by_artist_pair():
    plan = {
        "total_changes": 2,
        "changes": [
            _change("a.mp3", "chris brown", "Chris Brown"),
            _change("b.mp3", "chris brown", "Chris Brown"),
        ],
    }

    report = build_review_report(plan)

    assert "Total proposed changes: 2" in report
    assert "Current artist: chris brown" in report
    assert "New artist: Chris Brown" in report
    assert "Confidence: 95% (Capitalization difference only)" in report
    assert "a.mp3" in report
    assert "b.mp3" in report
    # Grouped under a single header, not repeated per file.
    assert report.count("Current artist: chris brown") == 1


def test_build_review_report_starts_new_section_per_artist_pair():
    plan = {
        "total_changes": 2,
        "changes": [
            _change("a.mp3", "chris brown", "Chris Brown"),
            _change("c.m4a", "JAY Z", "Jay-Z", confidence=85, reason="Word order difference"),
        ],
    }

    report = build_review_report(plan)

    assert report.count("Current artist:") == 2
    assert "Confidence: 85% (Word order difference)" in report


def test_save_review_report_writes_text(tmp_path):
    output_path = tmp_path / "change_report.txt"

    save_review_report("hello world", output_path)

    assert output_path.read_text() == "hello world"
