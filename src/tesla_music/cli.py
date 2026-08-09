import argparse
import time
from pathlib import Path

from tesla_music import analyzer
from tesla_music.scanner import scan_library
from tesla_music.recommendations import build_album_recommendations, build_recommendations
from tesla_music.feat_normalizer import find_featured_artist_changes
from tesla_music.planner import build_album_change_plan, build_change_plan, build_plan, save_plan
from tesla_music.reporter import (
    build_review_report,
    save_review_report,
)
from tesla_music.apply import (
    apply_changes,
    print_apply_report,
)
from tesla_music.flattener import (
    apply_flatten,
    build_flatten_plan,
    print_flatten_report,
)
from tesla_music.backup import list_backup_sessions
from tesla_music.restore import (
    apply_restore,
    build_restore_plan,
    print_restore_report,
)
from tesla_music.artwork import (
    LOW_CONFIDENCE_THRESHOLD,
    apply_artwork,
    build_artwork_plan,
    flatten_group,
    print_artwork_report,
)
from tesla_music.multi_artist import find_multi_artist_credits

def get_args():
    parser = argparse.ArgumentParser(
        description="Tesla Music Tools"
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply metadata changes"
    )

    parser.add_argument(
        "--show-files",
        action="store_true",
        help="List each song under its file format in the report"
    )

    parser.add_argument(
        "--flatten",
        action="store_true",
        help="Copy every song into a single flat folder (data/output/flattened)"
    )

    parser.add_argument(
        "--library",
        default=None,
        help="Path to your music library (default: data/input)"
    )

    parser.add_argument(
        "--restore",
        nargs="?",
        const="latest",
        default=None,
        metavar="SESSION",
        help="Restore files from a backup session (default: most recent). See --list-backups"
    )

    parser.add_argument(
        "--list-backups",
        action="store_true",
        help="List available backup sessions"
    )

    parser.add_argument(
        "--add-artwork",
        action="store_true",
        help="Search iTunes for missing album art and embed it"
    )

    return parser.parse_args()

def run_flatten(args):
    songs = scan_library(args.library)

    plan = build_flatten_plan(songs, "data/output/flattened")

    print()
    print(f"🎵 Flattening {plan['total_files']} songs into {plan['destination_folder']}")
    print("=====================================================")

    results = apply_flatten(plan, dry_run=not args.apply)

    print_flatten_report(results)

def run_list_backups():
    sessions = list_backup_sessions()

    print()
    if not sessions:
        print("No backup sessions found.")
        return

    print("Available backup sessions (most recent first):")
    print()

    for session in sessions:
        print(f"  {session}")

def run_restore(args):
    sessions = list_backup_sessions()

    if not sessions:
        print()
        print("❌ No backup sessions found in data/backups")
        return

    session = sessions[0] if args.restore == "latest" else args.restore

    if session not in sessions:
        print()
        print(f"❌ Backup session not found: {session}")
        print(f"Available sessions: {', '.join(sessions)}")
        return

    plan = build_restore_plan(session)

    print()
    print(f"🎵 Restoring {plan['total_files']} files from backup session {session}")
    print("=====================================================")

    results = apply_restore(plan, dry_run=not args.apply)

    print_restore_report(results)

def _print_progress(label, unit, start_time):
    def on_progress(completed, total):
        elapsed = time.time() - start_time
        rate = elapsed / completed if completed else 0
        eta_seconds = round(rate * (total - completed))
        percent = round(completed / total * 100) if total else 100

        print(
            f"\r{label}... {completed}/{total} {unit} "
            f"({percent}%) — ~{eta_seconds}s remaining",
            end="",
            flush=True,
        )

        if completed == total:
            print()

    return on_progress

def run_add_artwork(args):
    report = analyzer.run(args.library)

    plan = build_artwork_plan(
        report["artist_songs"],
        on_progress=_print_progress("Searching artwork", "albums/singles", time.time()),
    )

    print()
    print(f"🎨 Found artwork for {plan['total_files']} song(s) missing it")
    print("=====================================================")
    print()

    all_changes = []

    for group in plan["groups"]:
        label = group["album"] or f"(single) {group['songs'][0].title}"
        confidence = group["primary"]["confidence"]
        flag = " ⚠️  LOW CONFIDENCE" if confidence < LOW_CONFIDENCE_THRESHOLD else ""

        print(f"{group['artist']} — {label} — {confidence}% confidence{flag}")

        for song in group["songs"]:
            print(f"  - {song.path.name}")

        all_changes.extend(flatten_group(group))

    flat_plan = {"total_files": len(all_changes), "changes": all_changes}

    results = apply_artwork(
        flat_plan,
        dry_run=not args.apply,
        on_progress=_print_progress("Embedding artwork", "songs", time.time()),
    )

    print_artwork_report(results)

def main():
    args = get_args()
    print("🚗 Tesla Music Tools")
    print("--------------------")

    if args.list_backups:
        run_list_backups()
        return

    if args.restore:
        run_restore(args)
        return

    if args.library and not Path(args.library).is_dir():
        print(f"❌ Library path not found: {args.library}")
        return

    if args.flatten:
        run_flatten(args)
        return

    if args.add_artwork:
        run_add_artwork(args)
        return

    report = analyzer.run(args.library)

    print()
    print("🎵 Tesla Music Artist Report")
    print("===========================")
    print()

    print(f"Songs scanned: {report['songs_scanned']}")
    print()

    print("File Formats:")
    print()

    for extension, count in report["formats"].most_common():
        print(f"{extension.upper()}: {count} songs")

        if args.show_files:
            for song in report["format_songs"][extension]:
                print(f"  - {song.artist} - {song.title}")

        print()

    print("Artists:")
    print()

    for artist, count in report["artists"].most_common():
        print(f"{artist}: {count} songs")
        print()


    print("Recommended Changes:")
    print("====================")
    print()

    recommendations = build_recommendations(
        report["artist_groups"],
        report["artist_songs"],
    )
    
    if not recommendations:
        print("✅ Library is already clean. No changes recommended.")
        print()

    else:
        for recommendation in recommendations:
            print(
                f"Keep: {recommendation['keep']} "
                f"({recommendation['keep_count']} songs)"
            )
            print(
                f"  Confidence: {recommendation['confidence']}% "
                f"({recommendation['reason']})"
            )

            for change in recommendation["change"]:
                print(
                    f"  Change: {change['artist']} "
                    f"({change['count']} songs)"
                )
                
                print("    Files:")
                
                for song in change["songs"]:
                    print(f"      - {song.path.name}")
                    
            print()


    print("Featured Artist Cleanup:")
    print("========================")
    print()

    feat_changes = find_featured_artist_changes(report["artist_songs"])

    if not feat_changes:
        print("✅ No featured-artist tags found.")
        print()

    else:
        for change in feat_changes:
            print(Path(change["file"]).name)
            print(f"  Artist: {change['current_artist']} → {change['new_artist']}")
            print(f"  Title:  {change['current_title']} → {change['new_title']}")
            print()

    print("Album Name Cleanup:")
    print("====================")
    print()

    album_recommendations = build_album_recommendations(
        report["album_groups"], report["artist_songs"]
    )

    if not album_recommendations:
        print("✅ No duplicate album spellings found.")
        print()

    else:
        for recommendation in album_recommendations:
            print(
                f"{recommendation['artist']} — Keep: {recommendation['keep']} "
                f"({recommendation['keep_count']} songs)"
            )
            print(
                f"  Confidence: {recommendation['confidence']}% "
                f"({recommendation['reason']})"
            )

            for change in recommendation["change"]:
                print(
                    f"  Change: {change['album']} "
                    f"({change['count']} songs)"
                )

                for song in change["songs"]:
                    print(f"    - {song.path.name}")

            print()

    print("Multi-Artist Credits:")
    print("======================")
    print()

    multi_artist_candidates = find_multi_artist_credits(report["artist_songs"])

    if not multi_artist_candidates:
        print("✅ No ambiguous multi-artist credits found.")
        print()

    else:
        for candidate in multi_artist_candidates:
            print(f"{candidate['artist']} ({len(candidate['songs'])} songs)")
            print(f"  Parsed as: {', '.join(candidate['candidates'])}")

        print()
        print(
            f"{len(multi_artist_candidates)} credit(s) found. Each one could be a "
            "genuine duet, a group name, or a song that should feature one artist "
            "in the title — open the Streamlit app to review and decide each one."
        )
        print()

    dedup_changes = build_change_plan(recommendations)["changes"] if recommendations else []
    album_changes = (
        build_album_change_plan(album_recommendations)["changes"]
        if album_recommendations
        else []
    )
    all_changes = dedup_changes + feat_changes + album_changes

    if all_changes:
        plan = build_plan(all_changes)

        save_plan(
            plan,
            "data/output/change_plan.json"
    )

        review_report = build_review_report(plan)

        save_review_report(
            review_report,
            "data/output/change_report.txt"
    )


        apply_results = apply_changes(
            plan,
            dry_run=not args.apply,
    )

        print_apply_report(
            apply_results
    )

if __name__ == "__main__":
    main()
