from collections import Counter, defaultdict

from tesla_music.confidence import calculate_confidence


class _UnionFind:
    """
    Groups names that are similar to each other transitively, so if A~B and
    B~C are both flagged, all three end up in one cluster instead of two
    separate overlapping pairs (e.g. three spellings of the same artist
    showing up as three redundant merge suggestions).
    """

    def __init__(self, items):
        self._parent = {item: item for item in items}

    def find(self, item):
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]

        return item

    def union(self, a, b):
        root_a, root_b = self.find(a), self.find(b)

        if root_a != root_b:
            self._parent[root_a] = root_b


def cluster_similar_names(names):
    """
    Groups names that are similar to each other (transitively, via a
    union-find over calculate_confidence) into clusters, so three spellings
    of the same name end up in one cluster instead of three separate
    overlapping pairs. A cluster's score/reason come from its weakest
    pairwise edge -- if any one match in the cluster is only a guess, the
    whole cluster is treated that cautiously. Clusters of a single name
    (nothing to merge) are excluded.
    """
    names = list(names)
    union_find = _UnionFind(names)
    edges = defaultdict(list)

    for i, name1 in enumerate(names):
        for name2 in names[i + 1:]:
            confidence = calculate_confidence(name1, name2)

            if confidence["score"] > 0:
                union_find.union(name1, name2)
                edges[frozenset({name1, name2})].append(confidence)

    members_by_root = defaultdict(list)

    for name in names:
        members_by_root[union_find.find(name)].append(name)

    clusters = []

    for members in members_by_root.values():
        if len(members) < 2:
            continue

        cluster_edges = [
            confidence
            for pair, confidences in edges.items()
            if pair <= set(members)
            for confidence in confidences
        ]
        weakest = min(cluster_edges, key=lambda confidence: confidence["score"])

        clusters.append(
            {
                "members": members,
                "score": weakest["score"],
                "reason": weakest["reason"],
            }
        )

    return clusters


def _find_similar_names(name_counts):
    clusters = cluster_similar_names(name_counts.keys())

    return [
        {
            "names": [{"name": name, "count": name_counts[name]} for name in cluster["members"]],
            "score": cluster["score"],
            "reason": cluster["reason"],
        }
        for cluster in clusters
    ]


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


def find_similar_genres(genres):
    """
    Finds different spellings of the same genre across the whole library
    (e.g. "Hip-Hop", "Hip Hop", "hip hop") -- not scoped per artist or
    album, since a genre label means the same thing regardless of who's
    tagged with it.
    """
    groups = _find_similar_names(genres)

    return [
        {
            "genres": [{"genre": item["name"], "count": item["count"]} for item in group["names"]],
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
