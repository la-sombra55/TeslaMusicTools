def build_recommendations(duplicate_groups, artist_songs):
    recommendations = []

    for group in duplicate_groups:
        sorted_group = sorted(
            group["artists"],
            key=lambda x: x["count"],
            reverse=True,
        )

        keep = sorted_group[0]
        changes = sorted_group[1:]

        for change in changes:
            change["songs"] = artist_songs.get(
                change["artist"],
                []
            )

        recommendations.append(
            {
                "keep": keep["artist"],
                "keep_count": keep["count"],
                "change": changes,
                "confidence": group["score"],
                "reason": group["reason"],
            }
        )

    return recommendations