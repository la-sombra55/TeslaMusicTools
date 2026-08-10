from pathlib import Path

from tesla_music.backup import create_backup, new_backup_root, record_backup_library_path
from tesla_music.writer import update_tags


def _tag_updates(change):
    tags = {}

    if change.get("new_artist") is not None:
        tags["artist"] = change["new_artist"]

    if change.get("new_title") is not None:
        tags["title"] = change["new_title"]

    if change.get("new_album") is not None:
        tags["album"] = change["new_album"]

    return tags


def apply_changes(plan, dry_run=True, library_path=None):
    results = []
    backup_root = None if dry_run else new_backup_root()

    if backup_root is not None and library_path is not None:
        record_backup_library_path(backup_root, library_path)

    for change in plan["changes"]:
        file_path = change["file"]

        result = {
            "file": change["file"],
            "current_artist": change.get("current_artist"),
            "new_artist": change.get("new_artist"),
            "current_title": change.get("current_title"),
            "new_title": change.get("new_title"),
            "current_album": change.get("current_album"),
            "new_album": change.get("new_album"),
            "status": "pending",
        }

        if dry_run:
            result["status"] = "dry_run"

        else:
            try:
                backup = create_backup(file_path, backup_root)

                update_tags(
                    file_path,
                    _tag_updates(change),
                )

                result["backup"] = str(backup)
                result["status"] = "updated"

            except Exception as error:
                result["status"] = "failed"
                result["error"] = str(error)

        results.append(result)

    return results


def print_apply_report(results):
    print()
    print("🚗 Tesla Music Tools Apply Report")
    print("================================")
    print()

    successful = 0
    dry_runs = 0
    failed = 0

    for result in results:
        print("File:")
        print(f"  {Path(result['file']).name}")

        if result.get("new_artist") is not None:
            print(
                f"Artist: {result['current_artist']} → {result['new_artist']}"
            )

        if result.get("new_title") is not None:
            print(
                f"Title: {result['current_title']} → {result['new_title']}"
            )

        if result.get("new_album") is not None:
            print(
                f"Album: {result['current_album']} → {result['new_album']}"
            )

        print(
            f"Status: {result['status']}"
        )

        print()
        if result["status"] == "updated":
            successful += 1

        elif result["status"] == "dry_run":
            dry_runs += 1

        elif result["status"] == "failed":
            failed += 1

    print("Summary:")
    print("--------")
    print(f"Total files processed: {len(results)}")
    print(f"Successful updates: {successful}")
    print(f"Dry runs: {dry_runs}")
    print(f"Failed updates: {failed}")
