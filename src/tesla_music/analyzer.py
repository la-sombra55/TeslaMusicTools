from pathlib import Path
from collections import Counter

from mutagen import File


MUSIC_FOLDER = Path("data/input")

AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
}


def find_songs():
    songs = []

    for file in MUSIC_FOLDER.rglob("*"):
        if file.is_file() and file.suffix.lower() in AUDIO_EXTENSIONS:
            songs.append(file)

    return songs


def get_artist(song_path):
    try:
        audio = File(song_path, easy=True)

        if audio is None:
            return "Unknown"

        return audio.get("artist", ["Unknown"])[0]

    except Exception as error:
        print(f"⚠️ Could not read {song_path.name}: {error}")
        return "Unreadable"


def analyze_artists(songs):
    artists = Counter()

    for song in songs:
        artist = get_artist(song)
        artists[artist] += 1

    return artists


def run():
        songs = find_songs()
        
        print("🎵 Tesla Music Artist Report")
        print("===========================")
        print()

        print(f"Songs scanned: {len(songs)}")
        print()

        artists = analyze_artists(songs)

        print("Artists:")
        print()

        for artist, count in artists.most_common():
            print(f"{artist}: {count} songs")
            
if __name__ == "__main__":
    run()