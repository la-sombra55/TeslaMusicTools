from pathlib import Path
import shutil


def build_flatten_plan(file_paths, destination_folder):
    destination_folder = Path(destination_folder)

    changes = []
    used_names = set()

    for file_path in file_paths:
        file_path = Path(file_path)
        stem = file_path.stem
        extension = file_path.suffix

        candidate = file_path.name
        attempt = 2

        while candidate in used_names:
            candidate = f"{stem} ({attempt}){extension}"
            attempt += 1

        used_names.add(candidate)

        changes.append(
            {
                "source": str(file_path),
                "destination": str(destination_folder / candidate),
            }
        )

    return {
        "total_files": len(changes),
        "destination_folder": str(destination_folder),
        "changes": changes,
    }


def apply_flatten(plan, dry_run=True):
    results = []

    for change in plan["changes"]:
        result = {
            "source": change["source"],
            "destination": change["destination"],
            "status": "pending",
        }

        if dry_run:
            result["status"] = "dry_run"

        else:
            try:
                destination = Path(change["destination"])
                destination.parent.mkdir(parents=True, exist_ok=True)

                shutil.copy2(change["source"], destination)

                result["status"] = "copied"

            except Exception as error:
                result["status"] = "failed"
                result["error"] = str(error)

        results.append(result)

    return results


def print_flatten_report(results):
    print()
    print("🚗 Tesla Music Tools Flatten Report")
    print("===================================")
    print()

    copied = 0
    dry_runs = 0
    failed = 0

    for result in results:
        print(
            f"{Path(result['source']).name} → {Path(result['destination']).name}"
        )
        print(f"Status: {result['status']}")
        print()

        if result["status"] == "copied":
            copied += 1

        elif result["status"] == "dry_run":
            dry_runs += 1

        elif result["status"] == "failed":
            failed += 1

    print("Summary:")
    print("--------")
    print(f"Total files processed: {len(results)}")
    print(f"Copied: {copied}")
    print(f"Dry runs: {dry_runs}")
    print(f"Failed: {failed}")
