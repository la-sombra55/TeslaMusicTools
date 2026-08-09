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


def build_album_recommendations(album_groups_by_artist, artist_songs):
    recommendations = []

    for artist, groups in album_groups_by_artist.items():
        songs_by_album = {}

        for song in artist_songs.get(artist, []):
            songs_by_album.setdefault(song.album, []).append(song)

        for group in groups:
            sorted_group = sorted(
                group["albums"],
                key=lambda x: x["count"],
                reverse=True,
            )

            keep = sorted_group[0]
            changes = sorted_group[1:]

            for change in changes:
                change["songs"] = songs_by_album.get(change["album"], [])

            recommendations.append(
                {
                    "artist": artist,
                    "keep": keep["album"],
                    "keep_count": keep["count"],
                    "change": changes,
                    "confidence": group["score"],
                    "reason": group["reason"],
                }
            )

    return recommendations