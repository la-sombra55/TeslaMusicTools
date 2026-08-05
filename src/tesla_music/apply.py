from pathlib import Path

from tesla_music.backup import create_backup
from tesla_music.writer import update_artist


def apply_changes(plan, dry_run=True):
    results = []

    for change in plan["changes"]:
        file_path = change["file"]
        
        result = {
            "file": change["file"],
            "from": change["current_artist"],
            "to": change["new_artist"],
            "status": "pending",
        }

        if dry_run:
            result["status"] = "dry_run"
        
        else:
            try:
                backup = create_backup(file_path)
                
                update_artist(
                    file_path,
                    change["new_artist"],
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

        print(
            f"Artist: {result['from']} → {result['to']}"
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