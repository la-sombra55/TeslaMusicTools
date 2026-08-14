import csv

from tesla_music.csv_export import build_csv_rows, write_csv_export


def test_build_csv_rows_includes_expected_fields(make_song):
    artist_songs = {
        "Chris Brown": [
            make_song(
                "data/input/Chris Brown/Fortune/01 Turn Up.mp3",
                artist="Chris Brown",
                album_artist="Chris Brown",
                album="Fortune",
                title="Turn Up the Music",
                bitrate=320,
            )
        ]
    }

    rows = build_csv_rows(artist_songs)

    assert rows == [
        {
            "Title": "Turn Up the Music",
            "Artist": "Chris Brown",
            "Album": "Fortune",
            "Format": "mp3",
            "Bitrate (kbps)": 320,
        }
    ]


def test_build_csv_rows_shows_blank_bitrate_when_unknown(make_song):
    artist_songs = {"Chris Brown": [make_song("a.mp3", artist="Chris Brown", bitrate=0)]}

    rows = build_csv_rows(artist_songs)

    assert rows[0]["Bitrate (kbps)"] == ""


def test_build_csv_rows_lowercases_format_from_any_case_extension(make_song):
    artist_songs = {"2Pac": [make_song("a.M4A", artist="2Pac", title="Song")]}

    rows = build_csv_rows(artist_songs)

    assert rows[0]["Format"] == "m4a"


def test_build_csv_rows_covers_every_song_across_every_artist(make_song):
    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown"), make_song("b.mp3", artist="Chris Brown")],
        "Beyoncé": [make_song("c.mp3", artist="Beyoncé")],
    }

    rows = build_csv_rows(artist_songs)

    assert len(rows) == 3


def test_build_csv_rows_handles_no_songs():
    assert build_csv_rows({}) == []


def test_build_csv_rows_reports_progress(make_song):
    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown"), make_song("b.mp3", artist="Chris Brown")],
    }

    progress_calls = []

    build_csv_rows(artist_songs, on_progress=lambda done, total: progress_calls.append((done, total)))

    assert progress_calls == [(1, 2), (2, 2)]


def test_build_csv_rows_sorts_alphabetically_by_album(make_song):
    artist_songs = {
        "Chris Brown": [
            make_song("a.mp3", artist="Chris Brown", album="X"),
            make_song("b.mp3", artist="Chris Brown", album="Fortune"),
        ],
        "Beyoncé": [make_song("c.mp3", artist="Beyoncé", album="Lemonade")],
    }

    rows = build_csv_rows(artist_songs)

    assert [row["Album"] for row in rows] == ["Fortune", "Lemonade", "X"]


def test_build_csv_rows_sorts_albums_case_insensitively(make_song):
    artist_songs = {
        "Artist A": [make_song("a.mp3", artist="Artist A", album="zebra")],
        "Artist B": [make_song("b.mp3", artist="Artist B", album="Apple")],
    }

    rows = build_csv_rows(artist_songs)

    assert [row["Album"] for row in rows] == ["Apple", "zebra"]


def test_write_csv_export_writes_a_real_readable_csv(tmp_path):
    rows = [
        {
            "Title": "Turn Up the Music",
            "Artist": "Chris Brown",
            "Album": "Fortune",
            "Format": "mp3",
            "Bitrate (kbps)": 320,
        }
    ]
    destination = tmp_path / "export.csv"

    result = write_csv_export(rows, destination)

    assert result == destination
    assert destination.exists()

    with open(destination, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        read_rows = list(reader)

    assert read_rows == [{**rows[0], "Bitrate (kbps)": "320"}]


def test_write_csv_export_creates_missing_destination_folders(tmp_path):
    destination = tmp_path / "nested" / "deep" / "export.csv"

    write_csv_export([], destination)

    assert destination.exists()


def test_write_csv_export_writes_header_even_with_no_rows(tmp_path):
    destination = tmp_path / "export.csv"

    write_csv_export([], destination)

    with open(destination, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        assert reader.fieldnames == ["Title", "Artist", "Album", "Format", "Bitrate (kbps)"]
        assert list(reader) == []
