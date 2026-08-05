from collections import Counter

from tesla_music.metadata import read_metadata
from tesla_music.scanner import scan_library

def analyze_artists(song_files):
    artists = Counter()

    for file in song_files:
        song = read_metadata(file)

        if song:
            artists[song.artist] += 1

    return artists


def run():
    songs = scan_library()

    artists = analyze_artists(songs)

    return {
        "songs_scanned": len(songs),
        "artists": artists,
    }
