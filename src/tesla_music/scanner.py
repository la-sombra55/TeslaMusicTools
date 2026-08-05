from pathlib import Path
from collections import defaultdict, Counter


MUSIC_FOLDER = Path("data/input")

AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
}


def scan_library():
    library = []

    for file in MUSIC_FOLDER.rglob("*"):
        if file.is_file() and file.suffix.lower() in AUDIO_EXTENSIONS:
            library.append(file)

    return library


def build_report(songs):
    artists = defaultdict(list)
    file_types = Counter()

    for song in songs:
        parts = song.parts

        # Find folders relative to music directory
        relative = song.relative_to(MUSIC_FOLDER)

        folders = relative.parts

        if len(folders) >= 3:
            artist = folders[0]
            album = folders[1]

        elif len(folders) == 2:
            artist = folders[0]
            album = "Unknown"

        else:
            artist = "Unknown"
            album = "Unknown"

elif len(folders) == 2:
    artist = folders[0]
    album = "Unknown"

else:
    artist = "Unknown"
    album = "Unknown"

        artists[artist].append({
            "song": song.name,
            "album": album
        })

        file_types[song.suffix.lower()] += 1

    return artists, file_types


if __name__ == "__main__":
    songs = scan_library()
    artists, file_types = build_report(songs)

    print("🎵 Tesla Music Library Report")
    print("============================")
    print()

    print(f"Songs found: {len(songs)}")
    print(f"Artists found: {len(artists)}")
    print()

    print("Artists:")
    print()

    for artist, songs in artists.items():
        print(f"{artist}: {len(songs)} songs")

    print()
    print("File Types:")
    
    for extension, count in file_types.items():
        print(f"{extension}: {count}")