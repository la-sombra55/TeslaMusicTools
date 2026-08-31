import json
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

from mutagen.aiff import AIFF
from mutagen.id3 import ID3, ID3NoHeaderError, APIC
from mutagen.mp4 import MP4, MP4Cover
from mutagen.wave import WAVE

from tesla_music.backup import create_backup, new_backup_root, record_backup_library_path

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
DEEZER_ALBUM_SEARCH_URL = "https://api.deezer.com/search/album"
DEEZER_TRACK_SEARCH_URL = "https://api.deezer.com/search/track"
USER_AGENT = "TeslaMusicTools/0.1"
SEARCH_DELAY_SECONDS = 1
LOW_CONFIDENCE_THRESHOLD = 60


def has_artwork(file_path):
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".mp3":
        try:
            tags = ID3(file_path)
        except ID3NoHeaderError:
            return False

        return len(tags.getall("APIC")) > 0

    if suffix == ".m4a":
        audio = MP4(file_path)
        return bool(audio.get("covr"))

    if suffix == ".wav":
        audio = WAVE(file_path)
        return audio.tags is not None and len(audio.tags.getall("APIC")) > 0

    if suffix in (".aiff", ".aif"):
        audio = AIFF(file_path)
        return audio.tags is not None and len(audio.tags.getall("APIC")) > 0

    raise ValueError(f"Unsupported file type: {suffix}")


def embed_artwork(file_path, image_bytes, mime_type="image/jpeg"):
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".mp3":
        try:
            tags = ID3(file_path)
        except ID3NoHeaderError:
            tags = ID3()

        tags.delall("APIC")
        tags.add(
            APIC(
                encoding=3,
                mime=mime_type,
                type=3,
                desc="Cover",
                data=image_bytes,
            )
        )
        tags.save(file_path)

    elif suffix == ".m4a":
        audio = MP4(file_path)

        if audio is None:
            raise ValueError(f"Could not read {file_path.name}")

        cover_format = MP4Cover.FORMAT_PNG if mime_type == "image/png" else MP4Cover.FORMAT_JPEG
        audio["covr"] = [MP4Cover(image_bytes, imageformat=cover_format)]
        audio.save()

    elif suffix == ".wav":
        audio = WAVE(file_path)
        _embed_id3_frame_artwork(audio, image_bytes, mime_type)

    elif suffix in (".aiff", ".aif"):
        audio = AIFF(file_path)
        _embed_id3_frame_artwork(audio, image_bytes, mime_type)

    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _embed_id3_frame_artwork(audio, image_bytes, mime_type):
    if audio.tags is None:
        audio.add_tags()

    id3_tags = audio.tags
    assert id3_tags is not None

    id3_tags.delall("APIC")
    id3_tags.add(
        APIC(
            encoding=3,
            mime=mime_type,
            type=3,
            desc="Cover",
            data=image_bytes,
        )
    )
    audio.save()

    return True


def _similarity(expected, actual):
    return SequenceMatcher(None, expected.lower(), actual.lower()).ratio()


def _match_confidence(expected_artist, expected_target, actual_artist, actual_target):
    artist_score = _similarity(expected_artist, actual_artist)
    target_score = _similarity(expected_target, actual_target)

    return round(min(artist_score, target_score) * 100)


def _http_get_json(url, params):
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except Exception:
        return None


# --- Apple / iTunes Search API (primary source) ---


def _itunes_search(term, entity):
    data = _http_get_json(
        ITUNES_SEARCH_URL, {"term": term, "media": "music", "entity": entity, "limit": 1}
    )

    if data is None:
        return None

    results = data.get("results", [])

    if not results:
        return None

    return results[0]


def _artwork_url_from_result(result):
    artwork_url = result.get("artworkUrl100")

    if not artwork_url:
        return None

    return artwork_url.replace("100x100bb", "600x600bb")


def search_artwork(artist, album, title):
    if album and album != "Unknown":
        result = _itunes_search(f"{artist} {album}", entity="album")

        if result:
            artwork_url = _artwork_url_from_result(result)

            if artwork_url:
                confidence = _match_confidence(
                    artist, album, result.get("artistName", ""), result.get("collectionName", "")
                )
                return artwork_url, confidence

    result = _itunes_search(f"{artist} {title}", entity="song")

    if result:
        artwork_url = _artwork_url_from_result(result)

        if artwork_url:
            confidence = _match_confidence(
                artist, title, result.get("artistName", ""), result.get("trackName", "")
            )
            return artwork_url, confidence

    return None


# --- Deezer (alternate source) ---


def _deezer_search(url, term):
    data = _http_get_json(url, {"q": term, "limit": 1})

    if data is None:
        return None

    results = data.get("data", [])

    if not results:
        return None

    return results[0]


def search_artwork_alternate(artist, album, title):
    if album and album != "Unknown":
        result = _deezer_search(DEEZER_ALBUM_SEARCH_URL, f"{artist} {album}")

        if result:
            artwork_url = result.get("cover_big") or result.get("cover_medium")

            if artwork_url:
                confidence = _match_confidence(
                    artist, album, (result.get("artist") or {}).get("name", ""), result.get("title", "")
                )
                return artwork_url, confidence

    result = _deezer_search(DEEZER_TRACK_SEARCH_URL, f"{artist} {title}")

    if result:
        album_info = result.get("album") or {}
        artwork_url = album_info.get("cover_big") or album_info.get("cover_medium")

        if artwork_url:
            confidence = _match_confidence(
                artist, title, (result.get("artist") or {}).get("name", ""), result.get("title", "")
            )
            return artwork_url, confidence

    return None


# --- Planning ---


def _lookup_key(song):
    if song.album and song.album != "Unknown":
        return (song.artist, "album", song.album)

    return (song.artist, "title", song.title)


def _collect_lookup_targets(artist_songs):
    """
    Fast, network-free pass: groups songs missing artwork by lookup key.
    Returns (ordered list of keys, {key: [songs]}) so the caller knows the
    total amount of network work up front, before any of the slow part runs.
    """
    songs_by_key = {}
    order = []

    for songs in artist_songs.values():
        for song in songs:
            try:
                if has_artwork(song.path):
                    continue
            except Exception:
                continue

            lookup_key = _lookup_key(song)

            if lookup_key not in songs_by_key:
                songs_by_key[lookup_key] = []
                order.append(lookup_key)

            songs_by_key[lookup_key].append(song)

    return order, songs_by_key


def build_artwork_plan(artist_songs, on_progress=None):
    order, songs_by_key = _collect_lookup_targets(artist_songs)
    total_lookups = len(order)

    groups = []

    for index, lookup_key in enumerate(order):
        if index > 0:
            time.sleep(SEARCH_DELAY_SECONDS)

        songs = songs_by_key[lookup_key]
        representative = songs[0]

        match = search_artwork(representative.artist, representative.album, representative.title)

        if match is not None:
            artwork_url, confidence = match
            primary = {"artwork_url": artwork_url, "confidence": confidence, "source": "Apple"}

            alternate = None
            if confidence < LOW_CONFIDENCE_THRESHOLD:
                time.sleep(SEARCH_DELAY_SECONDS)
                alt_match = search_artwork_alternate(
                    representative.artist, representative.album, representative.title
                )

                if alt_match is not None:
                    alt_url, alt_confidence = alt_match
                    alternate = {
                        "artwork_url": alt_url,
                        "confidence": alt_confidence,
                        "source": "Deezer",
                    }

            groups.append(
                {
                    "artist": representative.artist,
                    "album": representative.album if representative.album != "Unknown" else None,
                    "songs": songs,
                    "primary": primary,
                    "alternate": alternate,
                }
            )

        if on_progress is not None:
            on_progress(index + 1, total_lookups)

    total_files = sum(len(group["songs"]) for group in groups)

    return {
        "total_files": total_files,
        "groups": groups,
    }


def flatten_group(group, use_alternate=False):
    chosen = group["primary"]

    if use_alternate and group["alternate"] is not None:
        chosen = group["alternate"]

    return [
        {"file": str(song.path), "artwork_url": chosen["artwork_url"]} for song in group["songs"]
    ]


# --- Applying ---


def _download_image(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read(), response.headers.get_content_type()


def apply_artwork(plan, dry_run=True, on_progress=None, library_path=None):
    results = []
    backup_root = None if dry_run else new_backup_root()
    total = len(plan["changes"])

    if backup_root is not None and library_path is not None:
        record_backup_library_path(backup_root, library_path)

    for index, change in enumerate(plan["changes"]):
        result = {
            "file": change["file"],
            "artwork_url": change["artwork_url"],
            "status": "pending",
        }

        if dry_run:
            result["status"] = "dry_run"

        else:
            try:
                backup = create_backup(change["file"], backup_root)

                image_bytes, mime_type = _download_image(change["artwork_url"])
                embed_artwork(change["file"], image_bytes, mime_type)

                result["backup"] = str(backup)
                result["status"] = "added"

            except Exception as error:
                result["status"] = "failed"
                result["error"] = str(error)

        results.append(result)

        if on_progress is not None:
            on_progress(index + 1, total)

    return results


def print_artwork_report(results):
    print()
    print("🚗 Tesla Music Tools Artwork Report")
    print("===================================")
    print()

    added = 0
    dry_runs = 0
    failed = 0

    for result in results:
        print(Path(result["file"]).name)
        print(f"Status: {result['status']}")
        print()

        if result["status"] == "added":
            added += 1

        elif result["status"] == "dry_run":
            dry_runs += 1

        elif result["status"] == "failed":
            failed += 1

    print("Summary:")
    print("--------")
    print(f"Total files processed: {len(results)}")
    print(f"Added: {added}")
    print(f"Dry runs: {dry_runs}")
    print(f"Failed: {failed}")
