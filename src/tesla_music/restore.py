from pathlib import Path
import shutil

from tesla_music.backup import LIBRARY_PATH_MARKER


def build_restore_plan(backup_session):
    backup_root = Path("data/backups") / backup_session

    if not backup_root.is_dir():
        raise ValueError(f"No backup session found: {backup_session}")

    changes = []

    for backup_file in sorted(backup_root.rglob("*")):
        if backup_file.is_file() and backup_file.name != LIBRARY_PATH_MARKER:
            original_path = backup_file.relative_to(backup_root)

            changes.append(
                {
                    "backup": str(backup_file),
                    "original": str(original_path),
                }
            )

    return {
        "backup_session": backup_session,
        "total_files": len(changes),
        "changes": changes,
    }


def apply_restore(plan, dry_run=True):
    results = []

    for change in plan["changes"]:
        result = {
            "backup": change["backup"],
            "original": change["original"],
            "status": "pending",
        }

        if dry_run:
            result["status"] = "dry_run"

        else:
            try:
                destination = Path(change["original"])
                destination.parent.mkdir(parents=True, exist_ok=True)

                shutil.copy2(change["backup"], destination)

                result["status"] = "restored"

            except Exception as error:
                result["status"] = "failed"
                result["error"] = str(error)

        results.append(result)

    return results


def print_restore_report(results):
    print()
    print("🚗 Tesla Music Tools Restore Report")
    print("===================================")
    print()

    restored = 0
    dry_runs = 0
    failed = 0

    for result in results:
        print(f"{Path(result['backup']).name} → {result['original']}")
        print(f"Status: {result['status']}")
        print()

        if result["status"] == "restored":
            restored += 1

        elif result["status"] == "dry_run":
            dry_runs += 1

        elif result["status"] == "failed":
            failed += 1

    print("Summary:")
    print("--------")
    print(f"Total files processed: {len(results)}")
    print(f"Restored: {restored}")
    print(f"Dry runs: {dry_runs}")
    print(f"Failed: {failed}")
