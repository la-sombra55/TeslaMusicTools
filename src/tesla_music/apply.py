from pathlib import Path

from tesla_music.backup import create_backup


def apply_changes(plan, dry_run=True):
    results = []

    for change in plan["changes"]:
        result = {
            "file": change["file"],
            "from": change["current_artist"],
            "to": change["new_artist"],
            "status": "pending",
        }

        if dry_run:
            result["status"] = "dry_run"
        
        else:
            backup = create_backup(change["file"])
            
            result["backup"] = str(backup)
            result["status"] = "backed_up"

        results.append(result)

    return results


def print_apply_report(results):
    print()
    print("🚗 Tesla Music Tools Apply Report")
    print("================================")
    print()

    for result in results:
        print(f"File:")
        print(f"  {Path(result['file']).name}")

        print(
            f"Artist:"
            f" {result['from']} → {result['to']}"
        )

        print(
            f"Status: {result['status']}"
        )

        print()