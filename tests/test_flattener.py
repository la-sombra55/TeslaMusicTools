from tesla_music.flattener import (
    apply_flatten,
    build_artist_folder_plan,
    build_flatten_plan,
    build_playlist_export_plan,
)


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


def test_build_artist_folder_plan_groups_songs_under_their_artist(make_song):
    artist_songs = {
        "Chris Brown": [
            make_song("Chris Brown/Fortune/01 Turn Up.mp3", artist="Chris Brown"),
            make_song("Chris Brown/Graffiti/02 Sing.mp3", artist="Chris Brown"),
        ],
        "Beyoncé": [make_song("Beyoncé/B'Day/01 Deja Vu.mp3", artist="Beyoncé")],
    }

    plan = build_artist_folder_plan(artist_songs, "data/output/by_artist")

    assert plan["total_files"] == 3
    destinations = {c["destination"] for c in plan["changes"]}
    assert destinations == {
        "data/output/by_artist/Chris Brown/01 Turn Up.mp3",
        "data/output/by_artist/Chris Brown/02 Sing.mp3",
        "data/output/by_artist/Beyoncé/01 Deja Vu.mp3",
    }


def test_build_artist_folder_plan_disambiguates_collisions_within_one_artist(make_song):
    artist_songs = {
        "2Pac": [
            make_song("2Pac/Album A/01 Intro.mp3", artist="2Pac"),
            make_song("2Pac/Album B/01 Intro.mp3", artist="2Pac"),
        ],
    }

    plan = build_artist_folder_plan(artist_songs, "out")

    destinations = [c["destination"] for c in plan["changes"]]
    assert destinations == [
        "out/2Pac/01 Intro.mp3",
        "out/2Pac/01 Intro (2).mp3",
    ]


def test_build_artist_folder_plan_sanitizes_slashes_in_artist_names(make_song):
    artist_songs = {
        "Fabolous/P. Diddy/Jagged Edge": [
            make_song("a.mp3", artist="Fabolous/P. Diddy/Jagged Edge")
        ],
    }

    plan = build_artist_folder_plan(artist_songs, "out")

    assert plan["changes"][0]["destination"] == "out/Fabolous-P. Diddy-Jagged Edge/a.mp3"


def test_build_artist_folder_plan_handles_no_songs():
    assert build_artist_folder_plan({}, "out") == {
        "total_files": 0,
        "destination_folder": "out",
        "changes": [],
    }


def test_build_playlist_export_plan_puts_songs_under_the_playlist_name(make_song):
    songs = [
        make_song("Lupe Fiasco/Food & Liquor/Kick Push.mp3", artist="Lupe Fiasco"),
        make_song("Kanye West/Late Registration/Touch the Sky.mp3", artist="Kanye West"),
    ]

    plan = build_playlist_export_plan(songs, "Road Trip", "data/output/playlists")

    assert plan["total_files"] == 2
    assert plan["destination_folder"] == "data/output/playlists/Road Trip"
    destinations = {c["destination"] for c in plan["changes"]}
    assert destinations == {
        "data/output/playlists/Road Trip/Kick Push.mp3",
        "data/output/playlists/Road Trip/Touch the Sky.mp3",
    }


def test_build_playlist_export_plan_disambiguates_name_collisions(make_song):
    songs = [
        make_song("Album A/01 Intro.mp3"),
        make_song("Album B/01 Intro.mp3"),
    ]

    plan = build_playlist_export_plan(songs, "Mix", "out")

    destinations = [c["destination"] for c in plan["changes"]]
    assert destinations == ["out/Mix/01 Intro.mp3", "out/Mix/01 Intro (2).mp3"]


def test_build_playlist_export_plan_sanitizes_slashes_in_playlist_name(make_song):
    songs = [make_song("a.mp3")]

    plan = build_playlist_export_plan(songs, "Rock/Pop Mix", "out")

    assert plan["destination_folder"] == "out/Rock-Pop Mix"


def test_build_playlist_export_plan_handles_no_songs():
    assert build_playlist_export_plan([], "Empty", "out") == {
        "total_files": 0,
        "destination_folder": "out/Empty",
        "changes": [],
    }


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


def test_apply_flatten_reports_progress(tmp_path):
    source_a = tmp_path / "a.mp3"
    source_b = tmp_path / "b.mp3"
    source_a.write_bytes(b"a")
    source_b.write_bytes(b"b")

    plan = {
        "total_files": 2,
        "destination_folder": str(tmp_path / "flat"),
        "changes": [
            {"source": str(source_a), "destination": str(tmp_path / "flat" / "a.mp3")},
            {"source": str(source_b), "destination": str(tmp_path / "flat" / "b.mp3")},
        ],
    }

    progress_calls = []

    apply_flatten(
        plan, dry_run=False, on_progress=lambda done, total: progress_calls.append((done, total))
    )

    assert progress_calls == [(1, 2), (2, 2)]


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
