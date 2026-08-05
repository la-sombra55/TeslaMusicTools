from dataclasses import dataclass
from pathlib import Path


@dataclass
class Song:
    path: Path

    artist: str = "Unknown"
    album_artist: str = "Unknown"
    album: str = "Unknown"
    title: str = "Unknown"

    def __str__(self):
        return (
            f"{self.artist} - {self.title}\n"
            f"Album: {self.album}\n"
            f"Album Artist: {self.album_artist}\n"
            f"File: {self.path.name}"
        )