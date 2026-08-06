import argparse
from pathlib import Path

from tesla_music import analyzer
from tesla_music.scanner import scan_library
from tesla_music.recommendations import build_recommendations
from tesla_music.feat_normalizer import find_featured_artist_changes
from tesla_music.planner import build_change_plan, build_plan, save_plan
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

    return parser.parse_args()

def run_flatten(args):
    songs = scan_library()

    plan = build_flatten_plan(songs, "data/output/flattened")

    print()
    print(f"🎵 Flattening {plan['total_files']} songs into {plan['destination_folder']}")
    print("=====================================================")

    results = apply_flatten(plan, dry_run=not args.apply)

    print_flatten_report(results)

def main():
    args = get_args()
    print("🚗 Tesla Music Tools")
    print("--------------------")

    if args.flatten:
        run_flatten(args)
        return

    report = analyzer.run()

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

    dedup_changes = build_change_plan(recommendations)["changes"] if recommendations else []
    all_changes = dedup_changes + feat_changes

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
