from pathlib import Path


MUSIC_FOLDER = Path("data/input")

AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
}


def scan_library():
    songs = []

    for file in MUSIC_FOLDER.rglob("*"):
        if file.is_file() and file.suffix.lower() in AUDIO_EXTENSIONS:
            songs.append(file)

    return songs


if __name__ == "__main__":
    songs = scan_library()

    print("🎵 Tesla Music Library Scan")
    print("-------------------------")
    print(f"Songs found: {len(songs)}")
    print()

    for song in songs:
        print(song)