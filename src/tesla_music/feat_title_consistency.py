from collections import defaultdict

from tesla_music.feat_normalizer import build_feat_title, split_featured_artist
from tesla_music.multi_artist import join_names, split_multi_artist
from tesla_music.normalizer import cluster_similar_names


def find_artist_spelling_groups(artist_songs):
    """
    Finds every spelling of an artist used anywhere in the library -- as a
    primary Artist tag, or as a featured credit inside another song's Title
    -- and clusters spellings that look like the same artist together, so
    the user can pick one preferred spelling to apply everywhere instead of
    the tool assuming whatever's already in the Artist tag is correct.
    """
    mentions = _collect_mentions(artist_songs)
    distinct_spellings = sorted({mention["spelling"] for mention in mentions})
    clusters = cluster_similar_names(distinct_spellings)

    groups = []

    for cluster in clusters:
        cluster_spellings = set(cluster["members"])
        cluster_mentions = [m for m in mentions if m["spelling"] in cluster_spellings]

        # Scoped to clusters that actually involve a featured-credit
        # mismatch -- a pure Artist-tag-vs-Artist-tag inconsistency with no
        # title credit involved is Duplicate Artist's job, not this tool's.
        if not any(m["source"] == "title_feat" for m in cluster_mentions):
            continue

        spellings = []

        for spelling in cluster["members"]:
            spelling_mentions = [m for m in cluster_mentions if m["spelling"] == spelling]
            spellings.append({"spelling": spelling, "mentions": spelling_mentions})

        spellings.sort(key=lambda s: len(s["mentions"]), reverse=True)

        groups.append(
            {
                "spellings": spellings,
                "total_count": len(cluster_mentions),
                "confidence": cluster["score"],
                "reason": cluster["reason"],
            }
        )

    return sorted(groups, key=lambda g: g["spellings"][0]["spelling"])


def build_artist_spelling_changes(preferred_spelling, group, artist_songs):
    """
    Builds the tag/title changes to standardize a spelling group onto
    preferred_spelling. Artist-tag mentions get a new Artist tag; title-feat
    mentions get just the credited name corrected within the title, leaving
    any other artist credited in that same title untouched.
    """
    changes = []
    title_corrections_by_file = defaultdict(dict)
    title_mentions_by_file = defaultdict(list)

    for spelling_entry in group["spellings"]:
        spelling = spelling_entry["spelling"]

        if spelling == preferred_spelling:
            continue

        for mention in spelling_entry["mentions"]:
            if mention["source"] == "artist_tag":
                changes.append(
                    {
                        "file": mention["file"],
                        "current_artist": spelling,
                        "new_artist": preferred_spelling,
                        "confidence": group["confidence"],
                        "reason": group["reason"],
                    }
                )
            else:
                title_corrections_by_file[mention["file"]][spelling] = preferred_spelling
                title_mentions_by_file[mention["file"]].append(mention)

    for file, corrections in title_corrections_by_file.items():
        song = title_mentions_by_file[file][0]["song"]
        base_title, featured_text = split_featured_artist(song.title)
        featured_names = split_multi_artist(featured_text) or [featured_text]
        corrected_names = [corrections.get(name, name) for name in featured_names]

        if corrected_names == featured_names:
            continue

        new_title = build_feat_title(base_title, join_names(corrected_names))

        changes.append(
            {
                "file": file,
                "current_title": song.title,
                "new_title": new_title,
                "confidence": group["confidence"],
                "reason": group["reason"],
            }
        )

    return changes


def _collect_mentions(artist_songs):
    mentions = []

    for artist, songs in artist_songs.items():
        for song in songs:
            mentions.append(
                {"spelling": artist, "source": "artist_tag", "file": str(song.path), "song": song}
            )

    for songs in artist_songs.values():
        for song in songs:
            split = split_featured_artist(song.title)

            if split is None:
                continue

            _, featured_text = split
            featured_names = split_multi_artist(featured_text) or [featured_text]

            for name in featured_names:
                mentions.append(
                    {"spelling": name, "source": "title_feat", "file": str(song.path), "song": song}
                )

    return mentions
