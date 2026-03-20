import csv
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

class UsabilityLogger:
    """
    Logs user interaction events for HCI usability studies.
    Focuses on capturing high-precision timestamps for 'Time on Task' analysis.
    """
    
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(UsabilityLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, subject_id: str = "pilot_user"):
        if self._initialized:
            return
            
        self.subject_id = subject_id
        self.session_id = str(uuid.uuid4())[:8]
        self.log_dir = Path.home() / ".modbusx" / "usability_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"session_{self.subject_id}_{timestamp_str}.csv"
        
        self._ensure_header()
        self._initialized = True
        
        self.log_event("SESSION_START", "App", f"Session ID: {self.session_id}")

    def _ensure_header(self):
        if not self.log_file.exists():
            with open(self.log_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp_iso", "timestamp_perf", "subject_id", "session_id", "event_type", "component", "details"])

    def log_event(self, event_type: str, component: str, details: str = ""):
        """
        Log a discrete event.
        
        Args:
            event_type: e.g., 'CLICK', 'DIALOG_OPEN', 'TASK_START', 'TASK_COMPLETE'
            component: The UI element or logical unit involved (e.g., 'BulkOpsDialog')
            details: Extra context (e.g., '10 registers added')
        """
        now_iso = datetime.now().isoformat()
        now_perf = time.perf_counter()
        
        try:
            with open(self.log_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([now_iso, now_perf, self.subject_id, self.session_id, event_type, component, details])
        except Exception as e:
            print(f"Failed to write to usability log: {e}")

    def start_task(self, task_name: str):
        self.log_event("TASK_START", "Task", task_name)

    def end_task(self, task_name: str, success: bool = True):
        status = "SUCCESS" if success else "FAILURE"
        self.log_event("TASK_END", "Task", f"{task_name}|{status}")

_logger_instance: Optional[UsabilityLogger] = None

def get_usability_logger(subject_id: str = "pilot_user") -> UsabilityLogger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = UsabilityLogger(subject_id)
    return _logger_instance
