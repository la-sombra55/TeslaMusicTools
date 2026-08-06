import json
from pathlib import Path

import pytest
from mutagen.id3 import ID3NoHeaderError

from tesla_music import artwork


class FakeID3Tags:
    def __init__(self, apic_frames):
        self._apic_frames = apic_frames
        self.saved_path = None

    def getall(self, key):
        return self._apic_frames if key == "APIC" else []

    def delall(self, key):
        if key == "APIC":
            self._apic_frames = []

    def add(self, frame):
        self._apic_frames.append(frame)

    def save(self, path):
        self.saved_path = path


class FakeMP4(dict):
    def save(self):
        pass


class FakeResponse:
    def __init__(self, payload_bytes, content_type="application/json"):
        self._payload = payload_bytes
        self._content_type = content_type

    class _Headers:
        def __init__(self, content_type):
            self._content_type = content_type

        def get_content_type(self):
            return self._content_type

    @property
    def headers(self):
        return self._Headers(self._content_type)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


# --- has_artwork ---


def test_has_artwork_true_when_apic_frame_present(monkeypatch):
    monkeypatch.setattr(artwork, "ID3", lambda path: FakeID3Tags(["fake_apic"]))

    assert artwork.has_artwork("song.mp3") is True


def test_has_artwork_false_when_no_apic_frame(monkeypatch):
    monkeypatch.setattr(artwork, "ID3", lambda path: FakeID3Tags([]))

    assert artwork.has_artwork("song.mp3") is False


def test_has_artwork_false_when_no_id3_header_at_all(monkeypatch):
    def raise_no_header(path):
        raise ID3NoHeaderError()

    monkeypatch.setattr(artwork, "ID3", raise_no_header)

    assert artwork.has_artwork("song.mp3") is False


def test_has_artwork_true_when_m4a_has_cover(monkeypatch):
    monkeypatch.setattr(artwork, "MP4", lambda path: FakeMP4(covr=[b"fake image bytes"]))

    assert artwork.has_artwork("song.m4a") is True


def test_has_artwork_false_when_m4a_has_no_cover(monkeypatch):
    monkeypatch.setattr(artwork, "MP4", lambda path: FakeMP4())

    assert artwork.has_artwork("song.m4a") is False


def test_has_artwork_raises_for_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        artwork.has_artwork("song.flac")


# --- embed_artwork ---


def test_embed_artwork_adds_apic_frame_for_mp3(monkeypatch):
    fake_tags = FakeID3Tags([])
    monkeypatch.setattr(artwork, "ID3", lambda path: fake_tags)

    artwork.embed_artwork("song.mp3", b"image bytes", "image/jpeg")

    assert len(fake_tags._apic_frames) == 1
    assert fake_tags.saved_path == Path("song.mp3")


def test_embed_artwork_creates_tags_when_no_id3_header_exists(monkeypatch):
    created = FakeID3Tags([])

    def fake_id3(path=None):
        if path is not None:
            raise ID3NoHeaderError()
        return created

    monkeypatch.setattr(artwork, "ID3", fake_id3)

    artwork.embed_artwork("song.mp3", b"image bytes")

    assert len(created._apic_frames) == 1


def test_embed_artwork_sets_covr_atom_for_m4a(monkeypatch):
    fake_audio = FakeMP4()
    monkeypatch.setattr(artwork, "MP4", lambda path: fake_audio)

    artwork.embed_artwork("song.m4a", b"image bytes", "image/png")

    assert len(fake_audio["covr"]) == 1


def test_embed_artwork_raises_for_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        artwork.embed_artwork("song.flac", b"bytes")


# --- _itunes_search / _artwork_url_from_result ---


def test_itunes_search_returns_top_result(monkeypatch):
    payload = json.dumps(
        {
            "resultCount": 1,
            "results": [{"artistName": "Chris Brown", "trackName": "Deuces"}],
        }
    ).encode()

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout=10: FakeResponse(payload)
    )

    result = artwork._itunes_search("Chris Brown Deuces", entity="song")

    assert result == {"artistName": "Chris Brown", "trackName": "Deuces"}


def test_itunes_search_returns_none_when_no_results(monkeypatch):
    payload = json.dumps({"resultCount": 0, "results": []}).encode()

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout=10: FakeResponse(payload)
    )

    assert artwork._itunes_search("Nonexistent Song", entity="song") is None


def test_itunes_search_returns_none_on_network_error(monkeypatch):
    def raise_error(request, timeout=10):
        raise OSError("network down")

    monkeypatch.setattr("urllib.request.urlopen", raise_error)

    assert artwork._itunes_search("Chris Brown", entity="song") is None


def test_artwork_url_from_result_upgrades_to_high_res():
    result = {"artworkUrl100": "https://example.com/100x100bb.jpg"}

    assert artwork._artwork_url_from_result(result) == "https://example.com/600x600bb.jpg"


def test_artwork_url_from_result_returns_none_when_missing():
    assert artwork._artwork_url_from_result({}) is None


# --- confidence scoring ---


def test_match_confidence_is_100_for_exact_match():
    confidence = artwork._match_confidence("Chris Brown", "Fortune", "Chris Brown", "Fortune")

    assert confidence == 100


def test_match_confidence_is_low_for_mismatched_artist():
    confidence = artwork._match_confidence("Chris Brown", "Fortune", "DaniLeigh", "Easy - Single")

    assert confidence < artwork.LOW_CONFIDENCE_THRESHOLD


def test_match_confidence_uses_the_weaker_of_the_two_scores():
    # Artist matches exactly but the target doesn't -> should be dragged down.
    confidence = artwork._match_confidence("Chris Brown", "Fortune", "Chris Brown", "Totally Different")

    assert confidence < 100


# --- search_artwork ---


def test_search_artwork_prefers_album_lookup(monkeypatch):
    calls = []

    def fake_itunes_search(term, entity):
        calls.append((term, entity))
        if entity == "album":
            return {"artworkUrl100": "https://example.com/album.jpg", "artistName": "Chris Brown", "collectionName": "Fortune"}
        return {"artworkUrl100": "https://example.com/song.jpg", "artistName": "Chris Brown", "trackName": "Turn Up the Music"}

    monkeypatch.setattr(artwork, "_itunes_search", fake_itunes_search)

    artwork_url, confidence = artwork.search_artwork("Chris Brown", "Fortune", "Turn Up the Music")

    assert artwork_url == "https://example.com/album.jpg"
    assert confidence == 100
    assert calls == [("Chris Brown Fortune", "album")]


def test_search_artwork_falls_back_to_song_when_album_unknown(monkeypatch):
    calls = []

    def fake_itunes_search(term, entity):
        calls.append((term, entity))
        return {"artworkUrl100": "https://example.com/song.jpg", "artistName": "Chris Brown", "trackName": "Deuces"}

    monkeypatch.setattr(artwork, "_itunes_search", fake_itunes_search)

    artwork_url, confidence = artwork.search_artwork("Chris Brown", "Unknown", "Deuces")

    assert artwork_url == "https://example.com/song.jpg"
    assert confidence == 100
    assert calls == [("Chris Brown Deuces", "song")]


def test_search_artwork_falls_back_when_album_lookup_finds_nothing(monkeypatch):
    def fake_itunes_search(term, entity):
        if entity == "album":
            return None
        return {"artworkUrl100": "https://example.com/song.jpg", "artistName": "Chris Brown", "trackName": "Some Title"}

    monkeypatch.setattr(artwork, "_itunes_search", fake_itunes_search)

    artwork_url, confidence = artwork.search_artwork("Chris Brown", "Some Album", "Some Title")

    assert artwork_url == "https://example.com/song.jpg"


def test_search_artwork_returns_none_when_nothing_found(monkeypatch):
    monkeypatch.setattr(artwork, "_itunes_search", lambda term, entity: None)

    assert artwork.search_artwork("Chris Brown", "Unknown", "Deuces") is None


# --- Deezer / search_artwork_alternate ---


def test_deezer_search_returns_top_result(monkeypatch):
    payload = json.dumps({"data": [{"title": "Fortune", "artist": {"name": "Chris Brown"}}]}).encode()

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout=10: FakeResponse(payload)
    )

    result = artwork._deezer_search(artwork.DEEZER_ALBUM_SEARCH_URL, "Chris Brown Fortune")

    assert result == {"title": "Fortune", "artist": {"name": "Chris Brown"}}


def test_deezer_search_returns_none_when_no_results(monkeypatch):
    payload = json.dumps({"data": []}).encode()

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout=10: FakeResponse(payload)
    )

    assert artwork._deezer_search(artwork.DEEZER_ALBUM_SEARCH_URL, "Nonexistent") is None


def test_search_artwork_alternate_prefers_album_lookup(monkeypatch):
    calls = []

    def fake_deezer_search(url, term):
        calls.append((url, term))
        if url == artwork.DEEZER_ALBUM_SEARCH_URL:
            return {"cover_big": "https://example.com/album.jpg", "artist": {"name": "Chris Brown"}, "title": "Fortune"}
        return {"album": {"cover_big": "https://example.com/song.jpg"}, "artist": {"name": "Chris Brown"}, "title": "Turn Up the Music"}

    monkeypatch.setattr(artwork, "_deezer_search", fake_deezer_search)

    artwork_url, confidence = artwork.search_artwork_alternate(
        "Chris Brown", "Fortune", "Turn Up the Music"
    )

    assert artwork_url == "https://example.com/album.jpg"
    assert confidence == 100
    assert calls == [(artwork.DEEZER_ALBUM_SEARCH_URL, "Chris Brown Fortune")]


def test_search_artwork_alternate_falls_back_to_track_when_album_unknown(monkeypatch):
    def fake_deezer_search(url, term):
        return {
            "album": {"cover_big": "https://example.com/song.jpg"},
            "artist": {"name": "Chris Brown"},
            "title": "Deuces",
        }

    monkeypatch.setattr(artwork, "_deezer_search", fake_deezer_search)

    artwork_url, confidence = artwork.search_artwork_alternate("Chris Brown", "Unknown", "Deuces")

    assert artwork_url == "https://example.com/song.jpg"
    assert confidence == 100


def test_search_artwork_alternate_returns_none_when_nothing_found(monkeypatch):
    monkeypatch.setattr(artwork, "_deezer_search", lambda url, term: None)

    assert artwork.search_artwork_alternate("Chris Brown", "Unknown", "Deuces") is None


# --- build_artwork_plan ---


def test_build_artwork_plan_skips_songs_that_already_have_artwork(make_song, monkeypatch):
    monkeypatch.setattr(artwork, "has_artwork", lambda path: True)
    monkeypatch.setattr(artwork, "search_artwork", lambda *a, **k: ("https://example.com/x.jpg", 100))

    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown", title="Deuces", album="F.A.M.E.")]
    }

    plan = artwork.build_artwork_plan(artist_songs)

    assert plan["total_files"] == 0
    assert plan["groups"] == []


def test_build_artwork_plan_includes_songs_missing_artwork(make_song, monkeypatch):
    monkeypatch.setattr(artwork, "has_artwork", lambda path: False)
    monkeypatch.setattr(artwork, "search_artwork", lambda *a, **k: ("https://example.com/x.jpg", 87))

    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown", title="Deuces", album="F.A.M.E.")]
    }

    plan = artwork.build_artwork_plan(artist_songs)

    assert plan["total_files"] == 1
    assert len(plan["groups"]) == 1
    group = plan["groups"][0]
    assert group["artist"] == "Chris Brown"
    assert group["album"] == "F.A.M.E."
    assert group["primary"] == {
        "artwork_url": "https://example.com/x.jpg",
        "confidence": 87,
        "source": "Apple",
    }
    assert group["alternate"] is None
    assert [s.title for s in group["songs"]] == ["Deuces"]


def test_build_artwork_plan_excludes_songs_with_no_artwork_found(make_song, monkeypatch):
    monkeypatch.setattr(artwork, "has_artwork", lambda path: False)
    monkeypatch.setattr(artwork, "search_artwork", lambda *a, **k: None)

    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown", title="Deuces", album="F.A.M.E.")]
    }

    plan = artwork.build_artwork_plan(artist_songs)

    assert plan["total_files"] == 0
    assert plan["groups"] == []


def test_build_artwork_plan_groups_songs_sharing_an_album(make_song, monkeypatch):
    monkeypatch.setattr(artwork, "has_artwork", lambda path: False)

    call_count = {"count": 0}

    def fake_search(artist, album, title):
        call_count["count"] += 1
        return "https://example.com/album.jpg", 90

    monkeypatch.setattr(artwork, "search_artwork", fake_search)

    artist_songs = {
        "Chris Brown": [
            make_song("a.mp3", artist="Chris Brown", title="Track 1", album="Fortune"),
            make_song("b.mp3", artist="Chris Brown", title="Track 2", album="Fortune"),
        ]
    }

    plan = artwork.build_artwork_plan(artist_songs)

    assert plan["total_files"] == 2
    assert len(plan["groups"]) == 1
    assert call_count["count"] == 1
    assert [s.title for s in plan["groups"][0]["songs"]] == ["Track 1", "Track 2"]


def test_build_artwork_plan_does_not_merge_different_albumless_singles(make_song, monkeypatch):
    # Regression test: two different singles by the same artist with no album
    # tag must NOT collapse into one cached lookup/group (they're different
    # songs and could have completely different artwork).
    monkeypatch.setattr(artwork.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(artwork, "has_artwork", lambda path: False)

    def fake_search(artist, album, title):
        return f"https://example.com/{title}.jpg", 90

    monkeypatch.setattr(artwork, "search_artwork", fake_search)

    artist_songs = {
        "Chris Brown": [
            make_song("a.mp3", artist="Chris Brown", title="Forever", album="Unknown"),
            make_song("b.mp3", artist="Chris Brown", title="Not My Fault", album="Unknown"),
        ]
    }

    plan = artwork.build_artwork_plan(artist_songs)

    assert plan["total_files"] == 2
    assert len(plan["groups"]) == 2
    urls = {group["primary"]["artwork_url"] for group in plan["groups"]}
    assert urls == {"https://example.com/Forever.jpg", "https://example.com/Not My Fault.jpg"}


def test_build_artwork_plan_auto_fetches_alternate_for_low_confidence(make_song, monkeypatch):
    monkeypatch.setattr(artwork.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(artwork, "has_artwork", lambda path: False)
    monkeypatch.setattr(artwork, "search_artwork", lambda *a, **k: ("https://example.com/apple.jpg", 20))
    monkeypatch.setattr(
        artwork, "search_artwork_alternate", lambda *a, **k: ("https://example.com/deezer.jpg", 95)
    )

    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown", title="Fortune", album="Fortune")]
    }

    plan = artwork.build_artwork_plan(artist_songs)

    group = plan["groups"][0]
    assert group["primary"]["confidence"] == 20
    assert group["alternate"] == {
        "artwork_url": "https://example.com/deezer.jpg",
        "confidence": 95,
        "source": "Deezer",
    }


def test_build_artwork_plan_does_not_fetch_alternate_for_high_confidence(make_song, monkeypatch):
    monkeypatch.setattr(artwork, "has_artwork", lambda path: False)
    monkeypatch.setattr(artwork, "search_artwork", lambda *a, **k: ("https://example.com/apple.jpg", 95))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("should not fetch an alternate for a high-confidence match")

    monkeypatch.setattr(artwork, "search_artwork_alternate", fail_if_called)

    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown", title="Fortune", album="Fortune")]
    }

    plan = artwork.build_artwork_plan(artist_songs)

    assert plan["groups"][0]["alternate"] is None


def test_build_artwork_plan_handles_no_alternate_found(make_song, monkeypatch):
    monkeypatch.setattr(artwork.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(artwork, "has_artwork", lambda path: False)
    monkeypatch.setattr(artwork, "search_artwork", lambda *a, **k: ("https://example.com/apple.jpg", 10))
    monkeypatch.setattr(artwork, "search_artwork_alternate", lambda *a, **k: None)

    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown", title="Fortune", album="Fortune")]
    }

    plan = artwork.build_artwork_plan(artist_songs)

    assert plan["groups"][0]["alternate"] is None


def test_build_artwork_plan_sleeps_between_distinct_lookups_but_not_before_first(
    make_song, monkeypatch
):
    monkeypatch.setattr(artwork, "has_artwork", lambda path: False)
    monkeypatch.setattr(artwork, "search_artwork", lambda *a, **k: ("https://example.com/x.jpg", 90))

    sleep_calls = []
    monkeypatch.setattr(artwork.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown", title="T1", album="Album A")],
        "Jay-Z": [make_song("b.mp3", artist="Jay-Z", title="T2", album="Album B")],
    }

    artwork.build_artwork_plan(artist_songs)

    assert sleep_calls == [artwork.SEARCH_DELAY_SECONDS]


def test_build_artwork_plan_reports_progress_once_per_lookup_with_known_total(
    make_song, monkeypatch
):
    monkeypatch.setattr(artwork.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(artwork, "has_artwork", lambda path: False)
    monkeypatch.setattr(artwork, "search_artwork", lambda *a, **k: ("https://example.com/x.jpg", 90))

    progress_calls = []

    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown", title="T1", album="Album A")],
        "Jay-Z": [make_song("b.mp3", artist="Jay-Z", title="T2", album="Album B")],
    }

    artwork.build_artwork_plan(artist_songs, on_progress=lambda done, total: progress_calls.append((done, total)))

    assert progress_calls == [(1, 2), (2, 2)]


def test_build_artwork_plan_progress_total_excludes_songs_that_already_have_artwork(
    make_song, monkeypatch
):
    monkeypatch.setattr(artwork, "has_artwork", lambda path: True)

    progress_calls = []

    artist_songs = {
        "Chris Brown": [make_song("a.mp3", artist="Chris Brown", title="T1", album="Album A")],
    }

    artwork.build_artwork_plan(artist_songs, on_progress=lambda done, total: progress_calls.append((done, total)))

    assert progress_calls == []


def test_build_artwork_plan_skips_songs_that_error_on_artwork_check(make_song, monkeypatch):
    def raise_error(path):
        raise ValueError("Unsupported file type: .flac")

    monkeypatch.setattr(artwork, "has_artwork", raise_error)

    artist_songs = {
        "Chris Brown": [make_song("a.flac", artist="Chris Brown", title="Track", album="Album")]
    }

    plan = artwork.build_artwork_plan(artist_songs)

    assert plan["total_files"] == 0


# --- flatten_group ---


def test_flatten_group_uses_primary_by_default(make_song):
    group = {
        "artist": "Chris Brown",
        "album": "Fortune",
        "songs": [make_song("a.mp3"), make_song("b.mp3")],
        "primary": {"artwork_url": "https://example.com/apple.jpg", "confidence": 90, "source": "Apple"},
        "alternate": None,
    }

    changes = artwork.flatten_group(group)

    assert changes == [
        {"file": "a.mp3", "artwork_url": "https://example.com/apple.jpg"},
        {"file": "b.mp3", "artwork_url": "https://example.com/apple.jpg"},
    ]


def test_flatten_group_uses_alternate_when_requested(make_song):
    group = {
        "artist": "Chris Brown",
        "album": "Fortune",
        "songs": [make_song("a.mp3")],
        "primary": {"artwork_url": "https://example.com/apple.jpg", "confidence": 20, "source": "Apple"},
        "alternate": {"artwork_url": "https://example.com/deezer.jpg", "confidence": 95, "source": "Deezer"},
    }

    changes = artwork.flatten_group(group, use_alternate=True)

    assert changes == [{"file": "a.mp3", "artwork_url": "https://example.com/deezer.jpg"}]


def test_flatten_group_falls_back_to_primary_when_alternate_requested_but_missing(make_song):
    group = {
        "artist": "Chris Brown",
        "album": "Fortune",
        "songs": [make_song("a.mp3")],
        "primary": {"artwork_url": "https://example.com/apple.jpg", "confidence": 20, "source": "Apple"},
        "alternate": None,
    }

    changes = artwork.flatten_group(group, use_alternate=True)

    assert changes == [{"file": "a.mp3", "artwork_url": "https://example.com/apple.jpg"}]


# --- apply_artwork ---


def test_apply_artwork_dry_run_does_not_touch_files(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("dry_run must not touch the filesystem")

    monkeypatch.setattr(artwork, "create_backup", fail_if_called)
    monkeypatch.setattr(artwork, "_download_image", fail_if_called)
    monkeypatch.setattr(artwork, "embed_artwork", fail_if_called)

    plan = {
        "total_files": 1,
        "changes": [{"file": "a.mp3", "artwork_url": "https://example.com/x.jpg"}],
    }

    results = artwork.apply_artwork(plan, dry_run=True)

    assert results[0]["status"] == "dry_run"


def test_apply_artwork_downloads_and_embeds_on_success(monkeypatch):
    monkeypatch.setattr(
        artwork, "create_backup", lambda file_path, backup_root: Path("data/backups/x/a.mp3")
    )
    monkeypatch.setattr(artwork, "_download_image", lambda url: (b"image bytes", "image/jpeg"))

    embedded = {}

    def fake_embed(file_path, image_bytes, mime_type):
        embedded["file_path"] = file_path
        embedded["image_bytes"] = image_bytes
        embedded["mime_type"] = mime_type
        return True

    monkeypatch.setattr(artwork, "embed_artwork", fake_embed)

    plan = {
        "total_files": 1,
        "changes": [{"file": "a.mp3", "artwork_url": "https://example.com/x.jpg"}],
    }

    results = artwork.apply_artwork(plan, dry_run=False)

    assert results[0]["status"] == "added"
    assert results[0]["backup"] == "data/backups/x/a.mp3"
    assert embedded == {
        "file_path": "a.mp3",
        "image_bytes": b"image bytes",
        "mime_type": "image/jpeg",
    }


def test_apply_artwork_records_failure_when_download_fails(monkeypatch):
    monkeypatch.setattr(
        artwork, "create_backup", lambda file_path, backup_root: Path("data/backups/x/a.mp3")
    )

    def raise_error(url):
        raise OSError("network down")

    monkeypatch.setattr(artwork, "_download_image", raise_error)

    plan = {
        "total_files": 1,
        "changes": [{"file": "a.mp3", "artwork_url": "https://example.com/x.jpg"}],
    }

    results = artwork.apply_artwork(plan, dry_run=False)

    assert results[0]["status"] == "failed"
    assert "network down" in results[0]["error"]


def test_print_artwork_report_summarizes_status_counts(capsys):
    results = [
        {"file": "a.mp3", "artwork_url": "x", "status": "added"},
        {"file": "b.mp3", "artwork_url": "x", "status": "dry_run"},
        {"file": "c.mp3", "artwork_url": "x", "status": "failed", "error": "boom"},
    ]

    artwork.print_artwork_report(results)

    output = capsys.readouterr().out
    assert "Total files processed: 3" in output
    assert "Added: 1" in output
    assert "Dry runs: 1" in output
    assert "Failed: 1" in output
