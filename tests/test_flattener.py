from tesla_music.flattener import apply_flatten, build_flatten_plan


def test_build_flatten_plan_keeps_original_filename():
    plan = build_flatten_plan(["nested/deep/07 Ballin.mp3"], "data/output/flattened")

    assert plan["total_files"] == 1
    assert plan["changes"][0]["destination"] == "data/output/flattened/07 Ballin.mp3"
    assert plan["changes"][0]["source"] == "nested/deep/07 Ballin.mp3"


def test_build_flatten_plan_disambiguates_name_collisions_from_different_folders():
    file_paths = [
        "Chris Brown/Fortune/01 Intro.mp3",
        "Chris Brown/Graffiti/01 Intro.mp3",
        "Jay-Z & Kanye West/Watch the Throne/01 Intro.mp3",
    ]

    plan = build_flatten_plan(file_paths, "out")

    destinations = [c["destination"] for c in plan["changes"]]
    assert destinations == [
        "out/01 Intro.mp3",
        "out/01 Intro (2).mp3",
        "out/01 Intro (3).mp3",
    ]


def test_build_flatten_plan_returns_empty_for_no_files():
    plan = build_flatten_plan([], "out")

    assert plan == {"total_files": 0, "destination_folder": "out", "changes": []}


def test_apply_flatten_dry_run_does_not_copy_files(tmp_path):
    source = tmp_path / "song.mp3"
    source.write_bytes(b"audio")

    plan = {
        "total_files": 1,
        "destination_folder": str(tmp_path / "flat"),
        "changes": [
            {
                "source": str(source),
                "destination": str(tmp_path / "flat" / "song.mp3"),
            }
        ],
    }

    results = apply_flatten(plan, dry_run=True)

    assert results[0]["status"] == "dry_run"
    assert not (tmp_path / "flat").exists()


def test_apply_flatten_copies_file_and_preserves_source(tmp_path):
    source = tmp_path / "song.mp3"
    source.write_bytes(b"audio bytes")
    destination = tmp_path / "flat" / "song.mp3"

    plan = {
        "total_files": 1,
        "destination_folder": str(tmp_path / "flat"),
        "changes": [{"source": str(source), "destination": str(destination)}],
    }

    results = apply_flatten(plan, dry_run=False)

    assert results[0]["status"] == "copied"
    assert destination.read_bytes() == b"audio bytes"
    assert source.read_bytes() == b"audio bytes"


def test_apply_flatten_records_failure_for_missing_source(tmp_path):
    plan = {
        "total_files": 1,
        "destination_folder": str(tmp_path / "flat"),
        "changes": [
            {
                "source": str(tmp_path / "does_not_exist.mp3"),
                "destination": str(tmp_path / "flat" / "x.mp3"),
            }
        ],
    }

    results = apply_flatten(plan, dry_run=False)

    assert results[0]["status"] == "failed"
    assert "error" in results[0]
