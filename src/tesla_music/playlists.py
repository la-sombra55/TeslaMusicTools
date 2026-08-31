import json
from pathlib import Path

from tesla_music.flattener import sanitize_folder_name

PLAYLISTS_FOLDER = Path("data/playlists")


SEARCH_FIELDS = {
    "artist": lambda song: song.artist,
    "title": lambda song: song.title,
    "album": lambda song: song.album,
}


def search_library(artist_songs, query, fields=("artist", "title")):
    """
    Finds songs where the search text appears in any of the given fields
    (case-insensitive, substring match). Defaults to Artist and Title --
    e.g. searching "Lupe Fiasco" catches both his own tracks and his
    features in other artists' titles. The manual-playlist picker searches
    Album too, since you're just trying to find a song, not necessarily by
    exact artist.
    """
    query = query.strip().lower()

    if not query:
        return []

    matches = []

    for songs in artist_songs.values():
        for song in songs:
            if any(query in SEARCH_FIELDS[field](song).lower() for field in fields):
                matches.append(song)

    return matches


def save_playlist(name, songs):
    PLAYLISTS_FOLDER.mkdir(parents=True, exist_ok=True)

    data = {"name": name, "songs": [str(song.path) for song in songs]}
    path = _playlist_path(name)
    path.write_text(json.dumps(data, indent=2))

    return path


def list_playlists():
    if not PLAYLISTS_FOLDER.is_dir():
        return []

    playlists = []

    for file in sorted(PLAYLISTS_FOLDER.glob("*.json")):
        try:
            data = json.loads(file.read_text())
        except (OSError, json.JSONDecodeError):
            continue

        playlists.append(data)

    return sorted(playlists, key=lambda playlist: playlist["name"].lower())


def delete_playlist(name):
    path = _playlist_path(name)

    if not path.is_file():
        return False

    path.unlink()

    return True


def resolve_playlist_songs(playlist, artist_songs):
    """
    Maps a saved playlist's file paths back to the current Song objects
    from a fresh import. Returns (found_songs, missing_paths) -- a song
    might be missing if the file was moved, renamed, or deleted since the
    playlist was saved.
    """
    song_by_path = {
        str(song.path): song for songs in artist_songs.values() for song in songs
    }

    found = []
    missing = []

    for path in playlist["songs"]:
        song = song_by_path.get(path)

        if song is not None:
            found.append(song)
        else:
            missing.append(path)

    return found, missing


def _playlist_path(name):
    return PLAYLISTS_FOLDER / f"{sanitize_folder_name(name)}.json"
