from pathlib import Path

from mutagen import File

from models import Song


def read_metadata(song_path: Path):
    song = Song(path=song_path)

    try:
        audio = File(song_path, easy=True)
    except Exception as error:
        print(f"Could not read {song_path.name}: {error}")
        return None

    if audio is None:
        return song

    song.artist = audio.get("artist", ["Unknown"])[0]
    song.album_artist = audio.get("albumartist", ["Unknown"])[0]
    song.album = audio.get("album", ["Unknown"])[0]
    song.title = audio.get("title", ["Unknown"])[0]

    return song


if __name__ == "__main__":
songs = scanner.find_songs()

first_song = songs[0]

song = read_metadata(first_song)

print(song)