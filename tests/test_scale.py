import time
from collections import Counter, defaultdict

from tesla_music.analyzer import analyze_formats
from tesla_music.feat_normalizer import find_featured_artist_changes
from tesla_music.flattener import build_flatten_plan
from tesla_music.normalizer import find_similar_artists
from tesla_music.planner import build_change_plan
from tesla_music.recommendations import build_recommendations


def _build_large_library(make_song, num_canonical_artists, songs_per_artist):
    """
    Synthetic library, no real audio files needed:
    - `num_canonical_artists` distinct artists, each with `songs_per_artist` songs
    - 9 out of 10 artists appear under two spellings (canonical + lowercase),
      which should be merged by dedup
    - every 10th artist is tagged with a "featuring" credit instead, which
      should be caught by feat-extraction rather than dedup
    - track filenames repeat across every artist's folder (e.g. every artist
      has a "005.mp3"), mirroring the real-world pattern of same-numbered
      tracks across many albums that flatten's collision handling exists for
    """
    artists = Counter()
    artist_songs = defaultdict(list)

    for i in range(num_canonical_artists):
        canonical = f"Artist {i:04d}"
        has_feat = i % 10 == 0

        variant_pool = (
            [f"{canonical} featuring Guest {i:04d}"]
            if has_feat
            else [canonical, canonical.lower()]
        )

        for song_index in range(songs_per_artist):
            variant = variant_pool[song_index % len(variant_pool)]
            song = make_song(
                f"{canonical}/album/{song_index:03d}.mp3",
                artist=variant,
                title=f"Track {song_index}",
            )
            artists[variant] += 1
            artist_songs[variant].append(song)

    return artists, artist_songs


def test_pipeline_handles_large_synthetic_library_correctly_and_quickly(make_song):
    num_artists = 500
    songs_per_artist = 20
    total_songs = num_artists * songs_per_artist

    artists, artist_songs = _build_large_library(make_song, num_artists, songs_per_artist)

    start = time.perf_counter()

    groups = find_similar_artists(artists)
    recommendations = build_recommendations(groups, artist_songs)
    dedup_plan = build_change_plan(recommendations)
    feat_changes = find_featured_artist_changes(artist_songs)
    formats, _ = analyze_formats(artist_songs)
    flatten_plan = build_flatten_plan(
        [song.path for songs in artist_songs.values() for song in songs],
        "out",
    )

    elapsed = time.perf_counter() - start

    feat_artist_count = len(range(0, num_artists, 10))
    dedup_artist_count = num_artists - feat_artist_count

    # Each of the two-spelling artists produces exactly one merge
    # recommendation (one pair of variants -> one confidence match). Songs
    # are split 50/50 across the two spellings, so only half need renaming
    # (the half under the spelling that isn't "kept").
    assert len(recommendations) == dedup_artist_count
    assert dedup_plan["total_changes"] == dedup_artist_count * (songs_per_artist // 2)

    # Each featuring-tagged artist's songs are caught by feat-extraction
    # instead of dedup.
    assert len(feat_changes) == feat_artist_count * songs_per_artist

    assert sum(formats.values()) == total_songs
    assert flatten_plan["total_files"] == total_songs

    # Regression guard against the artist-matching step's O(unique_artists^2)
    # comparisons, and flatten's collision handling, silently blowing up.
    assert elapsed < 10, f"Pipeline took {elapsed:.2f}s for {total_songs} songs"
