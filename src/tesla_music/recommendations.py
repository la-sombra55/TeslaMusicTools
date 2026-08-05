def build_recommendations(duplicate_groups):
    recommendations = []

    for group in duplicate_groups:
        sorted_group = sorted(
            group,
            key=lambda x: x["count"],
            reverse=True,
        )

        keep = sorted_group[0]
        changes = sorted_group[1:]

        recommendations.append(
            {
                "keep": keep["artist"],
                "keep_count": keep["count"],
                "change": changes,
            }
        )

    return recommendations