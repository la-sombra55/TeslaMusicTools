from datetime import datetime
from pathlib import Path
import shutil


def new_backup_root():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("data/backups") / timestamp


def _mirrored_path(file_path):
    file_path = Path(file_path)

    if file_path.is_absolute():
        file_path = file_path.relative_to(file_path.anchor)

    return file_path


def create_backup(file_path, backup_root=None):
    source = Path(file_path)

    if backup_root is None:
        backup_root = new_backup_root()

    destination = Path(backup_root) / _mirrored_path(source)

    destination.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source, destination)

    return destination


def list_backup_sessions():
    backups_root = Path("data/backups")

    if not backups_root.is_dir():
        return []

    sessions = [entry.name for entry in backups_root.iterdir() if entry.is_dir()]

    return sorted(sessions, reverse=True)
