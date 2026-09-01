from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Optional


@dataclass
class SOPStep:
    step: int
    timestamp: str
    application: str
    window: str
    screenshot: str
    note: str = ""


@dataclass
class SOPSession:
    title: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: int = 1
    steps: list[SOPStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "SOPSession":
        data = json.loads(path.read_text(encoding="utf-8"))
        data["steps"] = [SOPStep(**step) for step in data.get("steps", [])]
        return cls(**data)
