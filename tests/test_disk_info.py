import plistlib
from collections import namedtuple

from tesla_music import disk_info

FakeUsage = namedtuple("FakeUsage", ["total", "used", "free"])


class FakeCompletedProcess:
    def __init__(self, returncode, stdout=b""):
        self.returncode = returncode
        self.stdout = stdout


def _plist_bytes(**fields):
    return plistlib.dumps(fields)


def test_get_volume_status_walks_up_to_nearest_existing_ancestor(tmp_path, monkeypatch):
    # An export destination folder often doesn't exist yet -- the drive it
    # would be created on still does, so status should resolve against that.
    monkeypatch.setattr(
        disk_info.shutil, "disk_usage", lambda path: FakeUsage(total=1000, used=800, free=200)
    )
    monkeypatch.setattr(
        disk_info.subprocess,
        "run",
        lambda *a, **k: FakeCompletedProcess(
            0, _plist_bytes(RemovableMedia=True, Ejectable=True, Internal=False, VolumeName="MUSIC")
        ),
    )

    status = disk_info.get_volume_status(tmp_path / "not" / "created" / "yet")

    assert status["is_removable"] is True


def test_removable_check_uses_the_mount_point_not_a_deep_subfolder(tmp_path, monkeypatch):
    # diskutil only recognizes actual mount points -- "diskutil info
    # /Volumes/MUSIC/Music" fails outright even though that folder exists.
    # A real library path is almost always several folders below the mount
    # point, so the removable check has to walk up to it first.
    drive_root = tmp_path / "Volumes" / "MUSIC"
    library_path = drive_root / "Music" / "Artist" / "Album"
    library_path.mkdir(parents=True)

    monkeypatch.setattr(
        disk_info.shutil, "disk_usage", lambda path: FakeUsage(total=1000, used=800, free=200)
    )
    real_is_mount = disk_info.Path.is_mount
    monkeypatch.setattr(
        disk_info.Path,
        "is_mount",
        lambda self: self == drive_root or real_is_mount(self),
    )

    captured_paths = []

    def fake_run(command, **kwargs):
        captured_paths.append(command[-1])
        return FakeCompletedProcess(
            0, _plist_bytes(RemovableMedia=True, Ejectable=True, Internal=False, VolumeName="MUSIC")
        )

    monkeypatch.setattr(disk_info.subprocess, "run", fake_run)

    status = disk_info.get_volume_status(library_path)

    assert captured_paths == [str(drive_root)]
    assert status["is_removable"] is True


def test_get_volume_status_returns_none_when_disk_usage_fails(tmp_path, monkeypatch):
    def raise_error(path):
        raise OSError("no such device")

    monkeypatch.setattr(disk_info.shutil, "disk_usage", raise_error)

    assert disk_info.get_volume_status(tmp_path) is None


def test_get_volume_status_reports_removable_usb_drive(tmp_path, monkeypatch):
    monkeypatch.setattr(
        disk_info.shutil, "disk_usage", lambda path: FakeUsage(total=1000, used=800, free=200)
    )
    monkeypatch.setattr(
        disk_info.subprocess,
        "run",
        lambda *a, **k: FakeCompletedProcess(
            0, _plist_bytes(RemovableMedia=True, Ejectable=True, Internal=False, VolumeName="MUSIC")
        ),
    )

    status = disk_info.get_volume_status(tmp_path)

    assert status == {
        "total_bytes": 1000,
        "used_bytes": 800,
        "free_bytes": 200,
        "is_removable": True,
        "volume_name": "MUSIC",
    }


def test_get_volume_status_reports_internal_drive_as_not_removable(tmp_path, monkeypatch):
    monkeypatch.setattr(
        disk_info.shutil, "disk_usage", lambda path: FakeUsage(total=1000, used=800, free=200)
    )
    monkeypatch.setattr(
        disk_info.subprocess,
        "run",
        lambda *a, **k: FakeCompletedProcess(
            0,
            _plist_bytes(
                RemovableMedia=False, Ejectable=False, Internal=True, VolumeName="Macintosh HD"
            ),
        ),
    )

    status = disk_info.get_volume_status(tmp_path)

    assert status["is_removable"] is False
    assert status["volume_name"] == "Macintosh HD"


def test_get_volume_status_treats_diskutil_failure_as_not_removable(tmp_path, monkeypatch):
    monkeypatch.setattr(
        disk_info.shutil, "disk_usage", lambda path: FakeUsage(total=1000, used=800, free=200)
    )
    monkeypatch.setattr(
        disk_info.subprocess, "run", lambda *a, **k: FakeCompletedProcess(1, b"")
    )

    status = disk_info.get_volume_status(tmp_path)

    assert status["is_removable"] is False
    assert status["volume_name"] is None


def test_get_volume_status_handles_diskutil_being_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(
        disk_info.shutil, "disk_usage", lambda path: FakeUsage(total=1000, used=800, free=200)
    )

    def raise_error(*args, **kwargs):
        raise FileNotFoundError("no diskutil")

    monkeypatch.setattr(disk_info.subprocess, "run", raise_error)

    status = disk_info.get_volume_status(tmp_path)

    assert status["is_removable"] is False


def test_format_bytes_scales_units():
    assert disk_info.format_bytes(500) == "500 bytes"
    assert disk_info.format_bytes(2048) == "2.0 KB"
    assert disk_info.format_bytes(5 * 1024**2) == "5.0 MB"
    assert disk_info.format_bytes(27 * 1024**3) == "27.0 GB"
