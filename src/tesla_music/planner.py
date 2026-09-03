import json
from pathlib import Path


def build_change_plan(recommendations):
    changes = []

    for recommendation in recommendations:
        keep_artist = recommendation["keep"]
        confidence = recommendation["confidence"]
        reason = recommendation["reason"]

        for change in recommendation["change"]:
            current_artist = change["artist"]

            for song in change["songs"]:
                changes.append(
                    {
                        "file": str(song.path),
                        "current_artist": current_artist,
                        "new_artist": keep_artist,
                        "confidence": confidence,
                        "reason": reason,
                    }
                )

    return build_plan(changes)


def build_album_change_plan(recommendations):
    changes = []

    for recommendation in recommendations:
        artist = recommendation["artist"]
        keep_album = recommendation["keep"]
        confidence = recommendation["confidence"]
        reason = recommendation["reason"]

        for change in recommendation["change"]:
            current_album = change["album"]

            for song in change["songs"]:
                changes.append(
                    {
                        "file": str(song.path),
                        "artist": artist,
                        "current_album": current_album,
                        "new_album": keep_album,
                        "confidence": confidence,
                        "reason": reason,
                    }
                )

    return build_plan(changes)


def build_genre_change_plan(recommendations):
    changes = []

    for recommendation in recommendations:
        keep_genre = recommendation["keep"]
        confidence = recommendation["confidence"]
        reason = recommendation["reason"]

        for change in recommendation["change"]:
            current_genre = change["genre"]

            for song in change["songs"]:
                changes.append(
                    {
                        "file": str(song.path),
                        "current_genre": current_genre,
                        "new_genre": keep_genre,
                        "confidence": confidence,
                        "reason": reason,
                    }
                )

    return build_plan(changes)


def build_plan(changes):
    return {
        "total_changes": len(changes),
        "changes": changes,
    }


def save_plan(plan, output_path):
    output_path = Path(output_path)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            plan,
            file,
            indent=4,
        )