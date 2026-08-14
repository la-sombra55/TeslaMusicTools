from tesla_music.audio_quality import classify_bitrate, summarize_bitrate_quality


def test_classify_bitrate_below_256_is_low():
    assert classify_bitrate(128) == "low"
    assert classify_bitrate(255) == "low"


def test_classify_bitrate_between_256_and_300_is_standard():
    assert classify_bitrate(256) == "standard"
    assert classify_bitrate(300) == "standard"


def test_classify_bitrate_above_300_is_high():
    assert classify_bitrate(301) == "high"
    assert classify_bitrate(1411) == "high"


def test_classify_bitrate_zero_or_negative_is_unknown():
    assert classify_bitrate(0) == "unknown"
    assert classify_bitrate(-1) == "unknown"


def test_summarize_bitrate_quality_counts_each_bucket(make_song):
    artist_songs = {
        "Chris Brown": [
            make_song("a.mp3", artist="Chris Brown", bitrate=128),
            make_song("b.mp3", artist="Chris Brown", bitrate=256),
            make_song("c.mp3", artist="Chris Brown", bitrate=320),
            make_song("d.mp3", artist="Chris Brown", bitrate=0),
        ],
    }

    summary = summarize_bitrate_quality(artist_songs)

    assert summary["counts"] == {"low": 1, "standard": 1, "high": 1, "unknown": 1}


def test_summarize_bitrate_quality_collects_low_quality_songs(make_song):
    low_song = make_song("a.mp3", artist="Chris Brown", bitrate=128)
    artist_songs = {
        "Chris Brown": [
            low_song,
            make_song("b.mp3", artist="Chris Brown", bitrate=320),
        ],
    }

    summary = summarize_bitrate_quality(artist_songs)

    assert summary["low_quality_songs"] == [low_song]


def test_summarize_bitrate_quality_handles_no_songs():
    summary = summarize_bitrate_quality({})

    assert summary["counts"] == {"low": 0, "standard": 0, "high": 0, "unknown": 0}
    assert summary["low_quality_songs"] == []
