LOW_BITRATE_THRESHOLD_KBPS = 256
HIGH_BITRATE_THRESHOLD_KBPS = 300


def classify_bitrate(bitrate_kbps):
    if bitrate_kbps <= 0:
        return "unknown"

    if bitrate_kbps < LOW_BITRATE_THRESHOLD_KBPS:
        return "low"

    if bitrate_kbps > HIGH_BITRATE_THRESHOLD_KBPS:
        return "high"

    return "standard"


def summarize_bitrate_quality(artist_songs):
    """
    Buckets every song by audio quality: "low" (below 256kbps), "standard"
    (256-300kbps), "high" (above 300kbps), or "unknown" (bitrate couldn't be
    read). Returns counts plus the actual low-quality songs, since that's
    the group a user would actually want to look at and maybe replace.
    """
    counts = {"low": 0, "standard": 0, "high": 0, "unknown": 0}
    low_quality_songs = []

    for songs in artist_songs.values():
        for song in songs:
            quality = classify_bitrate(song.bitrate)
            counts[quality] += 1

            if quality == "low":
                low_quality_songs.append(song)

    return {
        "counts": counts,
        "low_quality_songs": low_quality_songs,
    }
