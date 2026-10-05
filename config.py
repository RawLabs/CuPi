import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from storage import StorageBackend, create_storage_backend

_DEFAULT_STORAGE = create_storage_backend()
CONFIG_DIR = _DEFAULT_STORAGE.layout.config
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "active_provider": "lmstudio",  # "lmstudio" or "openrouter"
    "lmstudio_url": "http://localhost:1234/v1",
    "lmstudio_model": "",
    "openrouter_url": "https://openrouter.ai/api/v1",
    "openrouter_key": "",
    "openrouter_model": "google/gemini-2.0-flash-001",
    "openrouter_privacy_accepted": False,
    "always_on_top": True,
    "max_history_turns": 10,
    "window_opacity": 100,
    "auto_save_captures": False,
    "captures_dir": str(_DEFAULT_STORAGE.layout.captures),
    "window_geometry": {
        "width": 460,
        "height": 720,
        "x": 100,
        "y": 100
    }
}


class ConfigManager:
    def __init__(self, storage: StorageBackend | None = None):
        self.storage = storage or _DEFAULT_STORAGE
        self.config_dir = self.storage.layout.config
        self.config_file = CONFIG_FILE
        if storage:
            self.config_file = self.config_dir / "config.json"
        self.defaults = deepcopy(DEFAULT_CONFIG)
        self.defaults["captures_dir"] = str(self.storage.layout.captures)
        self.last_error = ""
        self.data = self._load()

    def _load(self):
        if not self.config_file.exists():
            return deepcopy(self.defaults)
        try:
            if os.name == "posix":
                self.config_dir.chmod(0o700)
                self.config_file.chmod(0o600)
            with open(self.config_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config = deepcopy(self.defaults)
                if not isinstance(saved, dict):
                    raise ValueError("Configuration must be a JSON object")
                config.update(saved)
                return config
        except Exception as e:
            print(f"Error loading config, using defaults: {e}")
            return deepcopy(self.defaults)

    def save(self):
        temporary_path = None
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            if os.name == "posix":
                self.config_dir.chmod(0o700)
                if self.config_file.exists():
                    self.config_file.chmod(0o600)
            # NamedTemporaryFile starts with owner-only permissions. Replacement
            # leaves the previous valid configuration intact on a failed write.
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.config_dir,
                                             prefix=".config-", suffix=".tmp", delete=False) as handle:
                temporary_path = Path(handle.name)
                json.dump(self.data, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.config_file)
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = str(exc)
            print(f"Error saving config: {exc}")
            return False
        finally:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()
