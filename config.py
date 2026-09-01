import json
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
        self.data = self._load()

    def _load(self):
        if not self.config_file.exists():
            return dict(DEFAULT_CONFIG)
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config = dict(DEFAULT_CONFIG)
                config.update(saved)
                return config
        except Exception as e:
            print(f"Error loading config, using defaults: {e}")
            return dict(DEFAULT_CONFIG)

    def save(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()
