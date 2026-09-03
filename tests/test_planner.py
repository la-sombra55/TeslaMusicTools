import json

from tesla_music.planner import (
    build_album_change_plan,
    build_change_plan,
    build_genre_change_plan,
    save_plan,
)


def test_build_change_plan_flattens_songs_into_file_changes(make_song):
    recommendations = [
        {
            "keep": "Chris Brown",
            "keep_count": 97,
            "confidence": 95,
            "reason": "Capitalization difference only",
            "change": [
                {
                    "artist": "chris brown",
                    "count": 2,
                    "songs": [make_song("a.mp3"), make_song("b.mp3")],
                }
            ],
        }
    ]

    plan = build_change_plan(recommendations)

    assert plan["total_changes"] == 2
    assert plan["changes"] == [
        {
            "file": "a.mp3",
            "current_artist": "chris brown",
            "new_artist": "Chris Brown",
            "confidence": 95,
            "reason": "Capitalization difference only",
        },
        {
            "file": "b.mp3",
            "current_artist": "chris brown",
            "new_artist": "Chris Brown",
            "confidence": 95,
            "reason": "Capitalization difference only",
        },
    ]


def test_build_change_plan_handles_no_recommendations():
    plan = build_change_plan([])

    assert plan == {"total_changes": 0, "changes": []}


def test_build_album_change_plan_flattens_songs_into_file_changes(make_song):
    recommendations = [
        {
            "artist": "T.I.",
            "keep": "The KING",
            "keep_count": 15,
            "confidence": 95,
            "reason": "Capitalization difference only",
            "change": [
                {
                    "album": "The King",
                    "count": 1,
                    "songs": [make_song("b.mp3")],
                }
            ],
        }
    ]

    plan = build_album_change_plan(recommendations)

    assert plan["total_changes"] == 1
    assert plan["changes"] == [
        {
            "file": "b.mp3",
            "artist": "T.I.",
            "current_album": "The King",
            "new_album": "The KING",
            "confidence": 95,
            "reason": "Capitalization difference only",
        }
    ]


def test_build_album_change_plan_handles_no_recommendations():
    assert build_album_change_plan([]) == {"total_changes": 0, "changes": []}


def test_build_genre_change_plan_flattens_songs_into_file_changes(make_song):
    recommendations = [
        {
            "keep": "Hip-Hop",
            "keep_count": 120,
            "confidence": 85,
            "reason": "Word order difference",
            "change": [
                {
                    "genre": "Hip Hop",
                    "count": 15,
                    "songs": [make_song("a.mp3")],
                }
            ],
        }
    ]

    plan = build_genre_change_plan(recommendations)

    assert plan["total_changes"] == 1
    assert plan["changes"] == [
        {
            "file": "a.mp3",
            "current_genre": "Hip Hop",
            "new_genre": "Hip-Hop",
            "confidence": 85,
            "reason": "Word order difference",
        }
    ]


def test_build_genre_change_plan_handles_no_recommendations():
    assert build_genre_change_plan([]) == {"total_changes": 0, "changes": []}


def test_save_plan_writes_valid_json(tmp_path):
    plan = {"total_changes": 1, "changes": [{"file": "a.mp3"}]}
    output_path = tmp_path / "change_plan.json"

    save_plan(plan, output_path)

    assert json.loads(output_path.read_text()) == plan
