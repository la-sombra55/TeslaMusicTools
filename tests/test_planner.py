import json

from tesla_music.planner import build_change_plan, save_plan


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


def test_save_plan_writes_valid_json(tmp_path):
    plan = {"total_changes": 1, "changes": [{"file": "a.mp3"}]}
    output_path = tmp_path / "change_plan.json"

    save_plan(plan, output_path)

    assert json.loads(output_path.read_text()) == plan
