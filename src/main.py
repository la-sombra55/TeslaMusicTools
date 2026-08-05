from tesla_music import analyzer
from tesla_music.confidence import calculate_confidence


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


    print("Possible duplicates:")
    print()

    for group in report["artist_groups"]:
        print()

        first = group[0]["artist"]
        second = group[1]["artist"]

        confidence = calculate_confidence(first, second)

        print(
            f"🟢 {first} ↔ {second}"
    )

        print(
            f"Confidence: {confidence['score']}%"
    )

        print(
            f"Reason: {confidence['reason']}"
    )

        print()

if __name__ == "__main__":
    main()
