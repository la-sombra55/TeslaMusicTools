from collections import Counter, defaultdict

from tesla_music.normalizer import find_album_duplicates_by_artist, find_similar_artists
from tesla_music.metadata import read_metadata
from tesla_music.scanner import scan_library

def analyze_artists(songs, on_progress=None):
    artists = Counter()
    artist_songs = defaultdict(list)
    total = len(songs)

    for index, song_path in enumerate(songs):
        song = read_metadata(song_path)

        if song is not None:
            artists[song.artist] += 1
            artist_songs[song.artist].append(song)

        if on_progress is not None:
            on_progress(index + 1, total)

    return artists, artist_songs


def analyze_formats(artist_songs):
    formats = Counter()
    format_songs = defaultdict(list)

    for songs in artist_songs.values():
        for song in songs:
            extension = song.path.suffix.lower().lstrip(".")

            formats[extension] += 1
            format_songs[extension].append(song)

    return formats, format_songs


def run(library_path=None, on_progress=None):
    songs = scan_library(library_path)

    artists, artist_songs = analyze_artists(songs, on_progress=on_progress)
    formats, format_songs = analyze_formats(artist_songs)

    return {
    "songs_scanned": len(songs),
    "artists": artists,
    "artist_songs": artist_songs,
    "artist_groups": find_similar_artists(artists),
    "album_groups": find_album_duplicates_by_artist(artist_songs),
    "formats": formats,
    "format_songs": format_songs,
}
