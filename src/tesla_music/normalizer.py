from collections import Counter

from tesla_music.confidence import calculate_confidence


def _find_similar_names(name_counts):
    name_list = list(name_counts.items())

    groups = []

    for i, (name1, count1) in enumerate(name_list):

        for name2, count2 in name_list[i + 1:]:

            confidence = calculate_confidence(name1, name2)

            if confidence["score"] > 0:
                groups.append(
                    {
                        "names": [
                            {"name": name1, "count": count1},
                            {"name": name2, "count": count2},
                        ],
                        "score": confidence["score"],
                        "reason": confidence["reason"],
                    }
                )

    return groups


def find_similar_artists(artists):
    groups = _find_similar_names(artists)

    return [
        {
            "artists": [
                {"artist": item["name"], "count": item["count"]} for item in group["names"]
            ],
            "score": group["score"],
            "reason": group["reason"],
        }
        for group in groups
    ]


def find_album_duplicates_by_artist(artist_songs):
    """
    Detects similar album-name spellings within each artist's own songs
    (scoped per artist so unrelated artists sharing an album title, e.g.
    two different "Greatest Hits", never get compared to each other).
    """
    duplicates_by_artist = {}

    for artist, songs in artist_songs.items():
        album_counts = Counter(song.album for song in songs)
        groups = _find_similar_names(album_counts)

        if not groups:
            continue

        duplicates_by_artist[artist] = [
            {
                "albums": [
                    {"album": item["name"], "count": item["count"]} for item in group["names"]
                ],
                "score": group["score"],
                "reason": group["reason"],
            }
            for group in groups
        ]

    return duplicates_by_artist
