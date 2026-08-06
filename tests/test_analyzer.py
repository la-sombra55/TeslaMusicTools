from tesla_music.analyzer import analyze_formats


def test_analyze_formats_counts_songs_by_extension(make_song):
    artist_songs = {
        "Chris Brown": [make_song("a.mp3", title="A"), make_song("b.mp3", title="B")],
        "Jay-Z & Kanye West": [make_song("c.m4a", title="C")],
    }

    formats, format_songs = analyze_formats(artist_songs)

    assert formats == {"mp3": 2, "m4a": 1}
    assert [s.title for s in format_songs["mp3"]] == ["A", "B"]
    assert [s.title for s in format_songs["m4a"]] == ["C"]


def test_analyze_formats_lowercases_extension(make_song):
    artist_songs = {"Chris Brown": [make_song("a.MP3")]}

    formats, _ = analyze_formats(artist_songs)

    assert formats == {"mp3": 1}


def test_analyze_formats_handles_empty_library():
    formats, format_songs = analyze_formats({})

    assert formats == {}
    assert format_songs == {}
