from tesla_music import analyzer
from tesla_music.confidence import calculate_confidence
from tesla_music.recommendations import build_recommendations


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
