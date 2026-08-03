from pathlib import Path
from shutil import copy2


LEGACY_BACKUP_SUFFIX = ".pre-0.3.0"


def backup_legacy_file(path: str | Path) -> Path | None:
    source_path = Path(path)
    if not source_path.is_file():
        return None

    backup_path = source_path.with_name(f"{source_path.name}{LEGACY_BACKUP_SUFFIX}")
    if backup_path.exists():
        return None

    temporary_path = backup_path.parent / f".{backup_path.name}.tmp"
    copy2(source_path, temporary_path)
    temporary_path.replace(backup_path)

    return backup_path
