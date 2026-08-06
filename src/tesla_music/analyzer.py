from collections import Counter, defaultdict

from tesla_music.normalizer import find_similar_artists
from tesla_music.metadata import read_metadata
from tesla_music.scanner import scan_library

def analyze_artists(songs):
    artists = Counter()
    artist_songs = defaultdict(list)

    for song_path in songs:
        song = read_metadata(song_path)

        if song is None:
            continue

        artists[song.artist] += 1
        artist_songs[song.artist].append(song)

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


def run():
    songs = scan_library()

    artists, artist_songs = analyze_artists(songs)
    formats, format_songs = analyze_formats(artist_songs)

    return {
    "songs_scanned": len(songs),
    "artists": artists,
    "artist_songs": artist_songs,
    "artist_groups": find_similar_artists(artists),
    "formats": formats,
    "format_songs": format_songs,
}
