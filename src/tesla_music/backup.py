from pathlib import Path
import shutil
from datetime import datetime


def create_backup(file_path):
    source = Path(file_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_root = Path("data/backups") / timestamp

    backup_root.mkdir(
        parents=True,
        exist_ok=True
    )

    destination = backup_root / source.name

    shutil.copy2(
        source,
        destination
    )

    return destination