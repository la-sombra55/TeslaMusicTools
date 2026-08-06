from tesla_music.confidence import calculate_confidence


def find_similar_artists(artists):
    artist_list = list(artists.items())

    groups = []

    for i, (artist1, count1) in enumerate(artist_list):

        for artist2, count2 in artist_list[i + 1:]:

            confidence = calculate_confidence(artist1, artist2)

            if confidence["score"] > 0:
                groups.append(
                    {
                        "artists": [
                            {
                                "artist": artist1,
                                "count": count1,
                            },
                            {
                                "artist": artist2,
                                "count": count2,
                            },
                        ],
                        "score": confidence["score"],
                        "reason": confidence["reason"],
                    }
                )

    return groups
