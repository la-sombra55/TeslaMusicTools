from tesla_music import analyzer
from tesla_music.confidence import calculate_confidence
from tesla_music.recommendations import build_recommendations
from tesla_music.planner import build_change_plan, save_plan
from tesla_music.reporter import (
    build_review_report,
    save_review_report,
)


def main():
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
    plan = build_change_plan(recommendations)
    
    save_plan(
        plan,
        "data/output/change_plan.json",
    )
    
    review_report = build_review_report(plan)
    
    save_review_report(
        review_report,
        "data/output/change_report.txt",
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

if __name__ == "__main__":
    main()
