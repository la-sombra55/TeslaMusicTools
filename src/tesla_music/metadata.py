from pathlib import Path
from mutagen import File


def read_metadata(song_path: Path):
    try:
        audio = File(song_path, easy=True)
    except Exception as error:
        print(f"Could not read {song_path.name}: {error}")
        return None

    if audio is None:
        return None

    return {
        "file": song_path.name,
        "artist": audio.get("artist", ["Unknown"])[0],
        "album_artist": audio.get("albumartist", ["Unknown"])[0],
        "album": audio.get("album", ["Unknown"])[0],
        "title": audio.get("title", ["Unknown"])[0],
    }


if __name__ == "__main__":
    test_file = Path("data/input/1-04 Many Men (Wish Death).mp3")

    metadata = read_metadata(test_file)

    print(metadata)