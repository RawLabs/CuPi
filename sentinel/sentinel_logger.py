import time
from typing import List, Dict, Any
from storage import StorageBackend, create_storage_backend

class SentinelLogger:
    def __init__(self, log_filename: str = "sentinel_events.log", storage: StorageBackend | None = None):
        self.storage = storage or create_storage_backend()
        self.config_dir = self.storage.layout.logs
        self.log_path = self.config_dir / log_filename

        self.event_history: List[Dict[str, Any]] = []
        self.max_in_memory: int = 200
        self.candidate_count: int = 0

    def log_event(self, result, meta: Dict[str, Any]):
        timestamp_str = time.strftime("%H:%M:%S")
        state_name = result.state.name

        if result.state.name == "CANDIDATE":
            self.candidate_count += 1

        metrics = meta.get("metrics")
        proc_ms = meta.get("elapsed_ms", 0.0)

        entry = {
            "timestamp": timestamp_str,
            "state": state_name,
            "message": result.message,
            "frame_delta": result.frame_delta_ratio,
            "baseline_delta": result.baseline_delta_ratio,
            "elapsed_ms": proc_ms,
            "dropped": metrics.frames_dropped_busy if metrics else 0
        }

        self.event_history.append(entry)
        if len(self.event_history) > self.max_in_memory:
            self.event_history.pop(0)

        # Write to log file
        log_line = (
            f"[{timestamp_str}] [{state_name:<9}] {result.message} "
            f"(frame_delta={result.frame_delta_ratio*100:.1f}%, base_delta={result.baseline_delta_ratio*100:.1f}%, latency={proc_ms:.1f}ms)\n"
        )
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            print(f"Error writing to sentinel log file: {e}")

    def clear(self):
        self.event_history.clear()
        self.candidate_count = 0
        if self.log_path.exists():
            try:
                self.log_path.write_text("", encoding="utf-8")
            except Exception:
                pass
