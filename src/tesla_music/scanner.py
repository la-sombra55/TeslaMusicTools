from pathlib import Path


MUSIC_FOLDER = Path("data/input")

AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
}


def scan_library(folder=None):
    folder = Path(folder) if folder else MUSIC_FOLDER

    songs = []

    for file in folder.rglob("*"):
        if file.is_file() and file.suffix.lower() in AUDIO_EXTENSIONS:
            songs.append(file)

    return songs


if __name__ == "__main__":
    songs = scan_library()

    print(f"Songs found: {len(songs)}")

    for song in songs[:5]:
        print(song)