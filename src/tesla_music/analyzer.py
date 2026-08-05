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


def run():
    songs = scan_library()

    artists, artist_songs = analyze_artists(songs)

    return {
    "songs_scanned": len(songs),
    "artists": artists,
    "artist_songs": artist_songs,
    "artist_groups": find_similar_artists(artists),
}
