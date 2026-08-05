from pathlib import Path
import shutil
from datetime import datetime


def create_backup(file_path):
    file_path = Path(file_path)

    backup_root = Path("data/backups")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_folder = backup_root / timestamp
    backup_folder.mkdir(parents=True, exist_ok=True)

    destination = backup_folder / file_path.name

    shutil.copy2(file_path, destination)

    return destination