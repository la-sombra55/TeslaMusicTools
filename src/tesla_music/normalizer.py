from collections import defaultdict


def normalize_artist_name(artist):
    artist = artist.lower()

    artist = artist.replace("-", " ")

    words = artist.split()

    return set(words)


def find_similar_artists(artists):
    artist_list = list(artists.items())

    groups = []

    for i, (artist1, count1) in enumerate(artist_list):

        words1 = normalize_artist_name(artist1)

        for artist2, count2 in artist_list[i + 1:]:

            words2 = normalize_artist_name(artist2)

            if words1 == words2:
                groups.append(
                    [
                        {
                            "artist": artist1,
                            "count": count1,
                        },
                        {
                            "artist": artist2,
                            "count": count2,
                        },
                    ]
                )

    return groups