import csv
from pathlib import Path

CSV_FIELDNAMES = ["Title", "Artist", "Album", "Genre", "Grouping", "Format", "Bitrate (kbps)"]


def build_csv_rows(artist_songs, on_progress=None):
    rows = []
    total = sum(len(songs) for songs in artist_songs.values())
    completed = 0

    for songs in artist_songs.values():
        for song in songs:
            rows.append(
                {
                    "Title": song.title,
                    "Artist": song.artist,
                    "Album": song.album,
                    "Genre": song.genre,
                    "Grouping": song.grouping,
                    "Format": song.path.suffix.lower().lstrip("."),
                    "Bitrate (kbps)": song.bitrate or "",
                }
            )

            completed += 1

            if on_progress is not None:
                on_progress(completed, total)

    rows.sort(key=lambda row: row["Album"].lower())

    return rows


def write_csv_export(rows, destination_path):
    destination_path = Path(destination_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    with open(destination_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    return destination_path
