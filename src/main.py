import argparse
from tesla_music import analyzer
from tesla_music.recommendations import build_recommendations
from tesla_music.planner import build_change_plan, save_plan
from tesla_music.reporter import (
    build_review_report,
    save_review_report,
)
from tesla_music.apply import (
    apply_changes,
    print_apply_report,
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

    return parser.parse_args()

def main():
    args = get_args()
    print("🚗 Tesla Music Tools")
    print("--------------------")

    report = analyzer.run()

    print()
    print("🎵 Tesla Music Artist Report")
    print("===========================")
    print()

    print(f"Songs scanned: {report['songs_scanned']}")
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

    for recommendation in recommendations:
        print(
            f"Keep: {recommendation['keep']} "
            f"({recommendation['keep_count']} songs)"
         )

        for change in recommendation["change"]:
            print(
                f"  Change: {change['artist']} "
                f"({change['count']} songs)"
            )

            print("  Files:")

            for song in change["songs"]:
                print(f"    - {song.path.name}")

        print()


    plan = build_change_plan(recommendations)

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
