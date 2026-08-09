import shutil
from pathlib import Path

from tesla_music.metadata import read_metadata
from tesla_music.paths import mirrored_path
from tesla_music.scanner import scan_library

DRM_EXTENSIONS = {".m4p"}


def find_drm_songs(library_path=None):
    """
    Finds DRM-protected files (Apple's old FairPlay .m4p purchases) in the
    library. These can't be played in a Tesla and this tool will never write
    to them -- only reads title/artist for display here.
    """
    files = scan_library(library_path, extensions=DRM_EXTENSIONS)

    songs = []

    for file_path in files:
        song = read_metadata(file_path)

        if song is not None:
            songs.append(song)

    return songs


def build_drm_plan(songs, destination_folder="data/output/drm_review"):
    destination_folder = Path(destination_folder)
    changes = []

    for song in songs:
        changes.append(
            {
                "source": str(song.path),
                "destination": str(destination_folder / mirrored_path(song.path)),
                "artist": song.artist,
                "title": song.title,
            }
        )

    return {
        "total_files": len(changes),
        "changes": changes,
    }


def apply_drm_moves(plan, dry_run=True):
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

                shutil.move(change["source"], destination)

                result["status"] = "moved"

            except Exception as error:
                result["status"] = "failed"
                result["error"] = str(error)

        results.append(result)

    return results


def print_drm_report(results):
    print()
    print("🚗 Tesla Music Tools DRM File Report")
    print("====================================")
    print()

    moved = 0
    dry_runs = 0
    failed = 0

    for result in results:
        print(f"{Path(result['source']).name} → {result['destination']}")
        print(f"Status: {result['status']}")
        print()

        if result["status"] == "moved":
            moved += 1

        elif result["status"] == "dry_run":
            dry_runs += 1

        elif result["status"] == "failed":
            failed += 1

    print("Summary:")
    print("--------")
    print(f"Total files processed: {len(results)}")
    print(f"Moved: {moved}")
    print(f"Dry runs: {dry_runs}")
    print(f"Failed: {failed}")
