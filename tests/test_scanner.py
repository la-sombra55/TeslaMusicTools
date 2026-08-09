from tesla_music import scanner


def test_scan_library_finds_supported_audio_files_recursively(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "MUSIC_FOLDER", tmp_path)

    (tmp_path / "top.mp3").write_bytes(b"")
    nested = tmp_path / "Artist" / "Album"
    nested.mkdir(parents=True)
    (nested / "song.m4a").write_bytes(b"")
    (nested / "cover.jpg").write_bytes(b"")
    (nested / "notes.txt").write_bytes(b"")

    songs = scanner.scan_library()

    assert {song.name for song in songs} == {"top.mp3", "song.m4a"}


def test_scan_library_returns_empty_list_for_empty_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "MUSIC_FOLDER", tmp_path)

    assert scanner.scan_library() == []


def test_scan_library_accepts_explicit_folder_argument(tmp_path):
    (tmp_path / "top.mp3").write_bytes(b"")

    songs = scanner.scan_library(tmp_path)

    assert {song.name for song in songs} == {"top.mp3"}


def test_scan_library_explicit_folder_overrides_default(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "MUSIC_FOLDER", tmp_path / "should-not-be-used")
    (tmp_path / "top.mp3").write_bytes(b"")

    songs = scanner.scan_library(tmp_path)

    assert {song.name for song in songs} == {"top.mp3"}


def test_scan_library_default_extensions_exclude_m4p(tmp_path):
    (tmp_path / "top.mp3").write_bytes(b"")
    (tmp_path / "drm.m4p").write_bytes(b"")

    songs = scanner.scan_library(tmp_path)

    assert {song.name for song in songs} == {"top.mp3"}


def test_scan_library_accepts_custom_extensions(tmp_path):
    (tmp_path / "top.mp3").write_bytes(b"")
    (tmp_path / "drm.m4p").write_bytes(b"")

    songs = scanner.scan_library(tmp_path, extensions={".m4p"})

    assert {song.name for song in songs} == {"drm.m4p"}
