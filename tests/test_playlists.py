from datetime import datetime, timedelta

from tesla_music import playlists
from tesla_music.playlists import (
    delete_playlist,
    find_songs_added_between,
    list_playlists,
    resolve_playlist_songs,
    save_playlist,
    search_library,
)


# --- search_library ---


def test_search_library_matches_artist_field(make_song):
    lupe = make_song("a.mp3", artist="Lupe Fiasco", title="Kick Push")
    artist_songs = {"Lupe Fiasco": [lupe], "Kanye West": [make_song("b.mp3", artist="Kanye West")]}

    results = search_library(artist_songs, "Lupe Fiasco")

    assert results == [lupe]


def test_search_library_matches_title_field_too(make_song):
    # Catches a featured-artist credit inside another artist's song title.
    feature = make_song("c.mp3", artist="Ciara", title="Song (feat. Lupe Fiasco)")
    artist_songs = {"Ciara": [feature]}

    results = search_library(artist_songs, "Lupe Fiasco")

    assert results == [feature]


def test_search_library_does_not_match_album_by_default(make_song):
    song = make_song("a.mp3", artist="Lupe Fiasco", album="Food & Liquor")

    assert search_library({"Lupe Fiasco": [song]}, "Food & Liquor") == []


def test_search_library_matches_album_when_field_requested(make_song):
    song = make_song("a.mp3", artist="Lupe Fiasco", album="Food & Liquor")
    artist_songs = {"Lupe Fiasco": [song]}

    results = search_library(artist_songs, "Food & Liquor", fields=("artist", "title", "album"))

    assert results == [song]


def test_search_library_is_case_insensitive(make_song):
    song = make_song("a.mp3", artist="Lupe Fiasco")
    artist_songs = {"Lupe Fiasco": [song]}

    assert search_library(artist_songs, "lupe fiasco") == [song]
    assert search_library(artist_songs, "LUPE FIASCO") == [song]


def test_search_library_returns_empty_for_blank_query(make_song):
    artist_songs = {"Lupe Fiasco": [make_song("a.mp3", artist="Lupe Fiasco")]}

    assert search_library(artist_songs, "") == []
    assert search_library(artist_songs, "   ") == []


def test_search_library_returns_empty_for_no_matches(make_song):
    artist_songs = {"Lupe Fiasco": [make_song("a.mp3", artist="Lupe Fiasco")]}

    assert search_library(artist_songs, "Nonexistent Artist") == []


# --- save_playlist / list_playlists / delete_playlist ---


def test_save_and_list_playlist(tmp_path, monkeypatch, make_song):
    monkeypatch.setattr(playlists, "PLAYLISTS_FOLDER", tmp_path / "playlists")

    songs = [make_song("a.mp3", artist="Lupe Fiasco"), make_song("b.mp3", artist="Kanye West")]
    save_playlist("Road Trip", songs)

    saved = list_playlists()

    assert len(saved) == 1
    assert saved[0]["name"] == "Road Trip"
    assert saved[0]["songs"] == ["a.mp3", "b.mp3"]


def test_list_playlists_returns_empty_when_none_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(playlists, "PLAYLISTS_FOLDER", tmp_path / "playlists")

    assert list_playlists() == []


def test_list_playlists_sorted_alphabetically_case_insensitive(tmp_path, monkeypatch, make_song):
    monkeypatch.setattr(playlists, "PLAYLISTS_FOLDER", tmp_path / "playlists")

    save_playlist("zebra mix", [make_song("a.mp3")])
    save_playlist("Apple Mix", [make_song("b.mp3")])

    names = [p["name"] for p in list_playlists()]

    assert names == ["Apple Mix", "zebra mix"]


def test_save_playlist_sanitizes_slashes_in_filename(tmp_path, monkeypatch, make_song):
    monkeypatch.setattr(playlists, "PLAYLISTS_FOLDER", tmp_path / "playlists")

    save_playlist("Rock/Pop Mix", [make_song("a.mp3")])

    assert (tmp_path / "playlists" / "Rock-Pop Mix.json").exists()


def test_delete_playlist_removes_the_file(tmp_path, monkeypatch, make_song):
    monkeypatch.setattr(playlists, "PLAYLISTS_FOLDER", tmp_path / "playlists")

    save_playlist("Road Trip", [make_song("a.mp3")])
    assert delete_playlist("Road Trip") is True

    assert list_playlists() == []


def test_delete_playlist_returns_false_when_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(playlists, "PLAYLISTS_FOLDER", tmp_path / "playlists")

    assert delete_playlist("Does Not Exist") is False


# --- find_songs_added_between ---


def test_find_songs_added_between_includes_a_file_created_in_range(tmp_path, make_song):
    file_path = tmp_path / "a.mp3"
    file_path.write_bytes(b"")
    song = make_song(file_path, artist="Anna Merritt")
    artist_songs = {"Anna Merritt": [song]}

    now = datetime.now()
    matches = find_songs_added_between(artist_songs, now - timedelta(hours=1), now + timedelta(hours=1))

    assert matches == [song]


def test_find_songs_added_between_excludes_a_file_created_outside_range(tmp_path, make_song):
    file_path = tmp_path / "a.mp3"
    file_path.write_bytes(b"")
    song = make_song(file_path, artist="Anna Merritt")
    artist_songs = {"Anna Merritt": [song]}

    yesterday_start = datetime.now() - timedelta(days=2)
    yesterday_end = datetime.now() - timedelta(days=1)

    assert find_songs_added_between(artist_songs, yesterday_start, yesterday_end) == []


def test_find_songs_added_between_skips_files_that_no_longer_exist(make_song):
    song = make_song("does/not/exist.mp3", artist="Anna Merritt")
    artist_songs = {"Anna Merritt": [song]}

    now = datetime.now()

    assert find_songs_added_between(artist_songs, now - timedelta(hours=1), now + timedelta(hours=1)) == []


def test_find_songs_added_between_only_includes_songs_in_range_not_others(tmp_path, make_song):
    in_range_path = tmp_path / "a.mp3"
    in_range_path.write_bytes(b"")
    in_range_song = make_song(in_range_path, artist="Anna Merritt")

    out_of_range_song = make_song("does/not/exist.mp3", artist="Someone Else")

    artist_songs = {
        "Anna Merritt": [in_range_song],
        "Someone Else": [out_of_range_song],
    }

    now = datetime.now()
    matches = find_songs_added_between(artist_songs, now - timedelta(hours=1), now + timedelta(hours=1))

    assert matches == [in_range_song]


# --- resolve_playlist_songs ---


def test_resolve_playlist_songs_maps_paths_back_to_song_objects(make_song):
    song_a = make_song("a.mp3", artist="Lupe Fiasco")
    song_b = make_song("b.mp3", artist="Kanye West")
    artist_songs = {"Lupe Fiasco": [song_a], "Kanye West": [song_b]}
    playlist = {"name": "Road Trip", "songs": ["a.mp3", "b.mp3"]}

    found, missing = resolve_playlist_songs(playlist, artist_songs)

    assert found == [song_a, song_b]
    assert missing == []


def test_resolve_playlist_songs_reports_paths_no_longer_in_the_library(make_song):
    song_a = make_song("a.mp3", artist="Lupe Fiasco")
    artist_songs = {"Lupe Fiasco": [song_a]}
    playlist = {"name": "Road Trip", "songs": ["a.mp3", "moved-or-deleted.mp3"]}

    found, missing = resolve_playlist_songs(playlist, artist_songs)

    assert found == [song_a]
    assert missing == ["moved-or-deleted.mp3"]
