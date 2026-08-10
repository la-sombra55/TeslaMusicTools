from datetime import datetime
from pathlib import Path
import shutil

from tesla_music.paths import mirrored_path

# Written at the top of a backup session's folder to remember which library
# it came from, so sessions from different libraries (or different USB
# drives) can be told apart later. Excluded from file counts/restores since
# it isn't a backed-up song.
LIBRARY_PATH_MARKER = ".library_path"


def new_backup_root():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("data/backups") / timestamp


def record_backup_library_path(backup_root, library_path):
    backup_root = Path(backup_root)
    backup_root.mkdir(parents=True, exist_ok=True)

    marker_path = backup_root / LIBRARY_PATH_MARKER
    marker_path.write_text(str(Path(library_path).resolve()))


def get_backup_library_path(session):
    marker_path = Path("data/backups") / session / LIBRARY_PATH_MARKER

    if not marker_path.is_file():
        return None

    return marker_path.read_text().strip()


def create_backup(file_path, backup_root=None):
    source = Path(file_path)

    if backup_root is None:
        backup_root = new_backup_root()

    destination = Path(backup_root) / mirrored_path(source)

    destination.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source, destination)

    return destination


def list_backup_sessions():
    backups_root = Path("data/backups")

    if not backups_root.is_dir():
        return []

    sessions = [entry.name for entry in backups_root.iterdir() if entry.is_dir()]

    return sorted(sessions, reverse=True)


def count_backup_files(session):
    backup_root = Path("data/backups") / session

    if not backup_root.is_dir():
        return 0

    return sum(
        1 for entry in backup_root.rglob("*") if entry.is_file() and entry.name != LIBRARY_PATH_MARKER
    )
