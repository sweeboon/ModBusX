import json
import shutil
import time
from pathlib import Path
from PyQt5.QtCore import QObject, QTimer
from modbusx.logger import get_logger

class BackupManager(QObject):
    """
    Handles automatic configuration backups (NFR17).
    """
    def __init__(self, parent=None, backup_dir=None):
        super().__init__(parent)
        self.logger = get_logger("BackupManager")
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            self.backup_dir = Path.home() / ".modbusx" / "backups"
        
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._perform_backup)
        self._current_config_source = None

    def start_auto_backup(self, config_provider_callable, interval_min=10):
        """
        Start the auto-backup timer.
        :param config_provider_callable: Function that returns the current config dict
        :param interval_min: Interval in minutes
        """
        self._current_config_source = config_provider_callable
        # interval in ms
        self.timer.start(interval_min * 60 * 1000)
        self.logger.info(f"Auto-backup started. Interval: {interval_min} minutes.")

    def _perform_backup(self):
        if not self._current_config_source:
            return

        try:
            config_data = self._current_config_source()
            if not config_data:
                return

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"config_backup_{timestamp}.json"
            filepath = self.backup_dir / filename

            with open(filepath, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            self.logger.info(f"Auto-backup saved to {filepath}")
            
            # Cleanup old backups (keep last 5)
            self._cleanup_old_backups()
            
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")

    def _cleanup_old_backups(self):
        try:
            files = sorted(self.backup_dir.glob("config_backup_*.json"), key=lambda f: f.stat().st_mtime)
            while len(files) > 5:
                f = files.pop(0)
                f.unlink()
                self.logger.debug(f"Removed old backup: {f.name}")
        except Exception as e:
            self.logger.error(f"Backup cleanup error: {e}")
