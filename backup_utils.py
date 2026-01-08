import shutil
from datetime import datetime, timedelta
from pathlib import Path
from logging_utils import log

BACKUP_DIR = Path(__file__).parent / "backups"
DB_PATH = Path(__file__).parent / "bot_data.db"
RETENTION_DAYS = 7


def create_backup() -> Path | None:
    """Create a backup of the database. Returns backup path or None if DB doesn't exist."""
    if not DB_PATH.exists():
        log("[BACKUP] Database file not found, skipping backup", True, "warning")
        return None

    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = BACKUP_DIR / f"bot_data_{timestamp}.db"

    shutil.copy2(DB_PATH, backup_path)
    log(f"[BACKUP] Created: {backup_path.name}", True)
    return backup_path


def cleanup_old_backups() -> int:
    """Remove backups older than RETENTION_DAYS. Returns number of deleted files."""
    if not BACKUP_DIR.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted = 0

    for backup_file in BACKUP_DIR.glob("bot_data_*.db"):
        file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
        if file_time < cutoff:
            backup_file.unlink()
            log(f"[BACKUP] Deleted old backup: {backup_file.name}", True)
            deleted += 1

    return deleted


def run_backup():
    """Run backup and cleanup old backups."""
    create_backup()
    cleanup_old_backups()
