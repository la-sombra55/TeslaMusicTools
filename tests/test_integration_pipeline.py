from collections import Counter

from tesla_music.normalizer import find_similar_artists
from tesla_music.planner import build_change_plan
from tesla_music.recommendations import build_recommendations
from tesla_music.reporter import build_review_report


def test_full_pipeline_merges_chris_brown_case_variant(make_song):
    artists = Counter({"Chris Brown": 97, "chris brown": 2})
    artist_songs = {
        "Chris Brown": [make_song(f"cb_{i}.mp3") for i in range(97)],
        "chris brown": [make_song("dup_1.mp3"), make_song("dup_2.mp3")],
    }

    groups = find_similar_artists(artists)
    recommendations = build_recommendations(groups, artist_songs)
    plan = build_change_plan(recommendations)
    report = build_review_report(plan)

    assert plan["total_changes"] == 2
    assert all(c["new_artist"] == "Chris Brown" for c in plan["changes"])
    assert {c["file"] for c in plan["changes"]} == {"dup_1.mp3", "dup_2.mp3"}
    assert "Current artist: chris brown" in report
    assert "New artist: Chris Brown" in report
    assert "Confidence: 95% (Capitalization difference only)" in report


def test_full_pipeline_merges_jay_z_hyphen_and_spacing_variants(make_song):
    artists = Counter({"Jay-Z & Kanye West": 60, "JAY Z & Kanye West": 1})
    artist_songs = {
        "Jay-Z & Kanye West": [make_song(f"wtt_{i}.m4a") for i in range(60)],
        "JAY Z & Kanye West": [make_song("Who Gon Stop Me.m4a")],
    }

    groups = find_similar_artists(artists)
    recommendations = build_recommendations(groups, artist_songs)
    plan = build_change_plan(recommendations)

    assert plan["total_changes"] == 1
    assert plan["changes"][0] == {
        "file": "Who Gon Stop Me.m4a",
        "current_artist": "JAY Z & Kanye West",
        "new_artist": "Jay-Z & Kanye West",
        "confidence": 85,
        "reason": "Word order difference",
    }


def test_full_pipeline_produces_no_changes_for_a_clean_library(make_song):
    artists = Counter({"Chris Brown": 99, "Chris Brown & Tyga": 18, "50 Cent": 1})
    artist_songs = {}

    groups = find_similar_artists(artists)
    recommendations = build_recommendations(groups, artist_songs)
    plan = build_change_plan(recommendations)

    assert recommendations == []
    assert plan["total_changes"] == 0
