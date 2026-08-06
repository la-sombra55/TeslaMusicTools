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