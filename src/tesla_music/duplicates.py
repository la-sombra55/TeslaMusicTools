import re
import shutil
from collections import defaultdict
from pathlib import Path

from mutagen import File

from tesla_music.confidence import normalize
from tesla_music.scanner import AUDIO_EXTENSIONS

DUPLICATE_SCAN_EXTENSIONS = AUDIO_EXTENSIONS | {".m4p"}
DURATION_TOLERANCE_SECONDS = 2
DUPLICATE_SUFFIX_PATTERN = re.compile(r"\s(\d+|\(\d+\))$")


def _get_duration(file_path):
    try:
        audio = File(file_path)

        if audio is None or audio.info is None:
            return None

        return audio.info.length

    except Exception:
        return None


def _cluster_by_duration(entries):
    known = sorted((entry for entry in entries if entry[1] is not None), key=lambda e: e[1])

    clusters = []
    current = []

    for entry in known:
        if current and entry[1] - current[-1][1] > DURATION_TOLERANCE_SECONDS:
            clusters.append(current)
            current = []

        current.append(entry)

    if current:
        clusters.append(current)

    return clusters


def find_duplicate_songs(artist_songs):
    """
    Finds likely-duplicate songs within each artist's own catalog: same
    normalized title, and duration within a couple seconds of each other.
    Scoped per artist so two unrelated songs that happen to share a generic
    title (e.g. "Intro") by different artists are never compared.
    """
    duplicate_groups = []

    for artist, songs in artist_songs.items():
        titles = defaultdict(list)

        for song in songs:
            titles[normalize(song.title)].append((song, _get_duration(song.path)))

        for entries in titles.values():
            if len(entries) < 2:
                continue

            for cluster in _cluster_by_duration(entries):
                if len(cluster) < 2:
                    continue

                duplicate_groups.append(
                    {
                        "artist": artist,
                        "title": cluster[0][0].title,
                        "songs": [song for song, duration in cluster],
                    }
                )

    return duplicate_groups


def _file_preference_score(song):
    score = 0

    if song.path.suffix.lower() != ".m4p":
        score += 10

    if not DUPLICATE_SUFFIX_PATTERN.search(song.path.stem):
        score += 5

    try:
        score += song.path.stat().st_size / 1_000_000
    except OSError:
        pass

    return score


def _mirrored_path(file_path):
    file_path = Path(file_path)

    if file_path.is_absolute():
        file_path = file_path.relative_to(file_path.anchor)

    return file_path


def build_duplicate_plan(duplicate_groups, destination_folder="data/output/duplicates_review"):
    destination_folder = Path(destination_folder)
    changes = []

    for group in duplicate_groups:
        sorted_songs = sorted(group["songs"], key=_file_preference_score, reverse=True)
        keep = sorted_songs[0]
        duplicate_songs = sorted_songs[1:]

        for duplicate_song in duplicate_songs:
            changes.append(
                {
                    "source": str(duplicate_song.path),
                    "destination": str(destination_folder / _mirrored_path(duplicate_song.path)),
                    "keep": str(keep.path),
                    "artist": group["artist"],
                    "title": group["title"],
                }
            )

    return {
        "total_files": len(changes),
        "changes": changes,
    }


def apply_duplicate_moves(plan, dry_run=True):
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


def print_duplicate_report(results):
    print()
    print("🚗 Tesla Music Tools Duplicate Report")
    print("=====================================")
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
