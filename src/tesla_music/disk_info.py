import plistlib
import shutil
import subprocess
from pathlib import Path


def get_volume_status(path):
    """
    Returns disk usage and removable-media info for the volume containing
    `path`, or None if it can't be determined. Walks up to the nearest
    existing ancestor first, since an export destination folder often
    doesn't exist yet -- the drive it would be created on still does.
    """
    path = Path(path)

    while not path.exists():
        parent = path.parent

        if parent == path:
            return None

        path = parent

    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None

    is_removable, volume_name = _removable_volume_info(path)

    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "is_removable": is_removable,
        "volume_name": volume_name,
    }


def _removable_volume_info(path):
    # diskutil only recognizes actual mount points, not arbitrary folders
    # inside one -- "diskutil info /Volumes/MUSIC/Music" fails outright
    # even though /Volumes/MUSIC/Music is a real, existing folder.
    mount_point = _find_mount_point(path)

    try:
        result = subprocess.run(
            ["diskutil", "info", "-plist", str(mount_point)],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        return False, None

    if result.returncode != 0:
        return False, None

    try:
        info = plistlib.loads(result.stdout)
    except Exception:
        return False, None

    is_removable = bool(info.get("RemovableMedia")) or bool(info.get("Ejectable")) or not bool(
        info.get("Internal", True)
    )

    return is_removable, info.get("VolumeName")


def _find_mount_point(path):
    path = path.resolve()

    while not path.is_mount():
        parent = path.parent

        if parent == path:
            return path

        path = parent

    return path


def format_bytes(num_bytes):
    size = float(num_bytes)

    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)} {unit}" if unit == "bytes" else f"{size:.1f} {unit}"

        size /= 1024
