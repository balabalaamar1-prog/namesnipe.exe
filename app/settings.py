"""Tiny JSON settings store in %APPDATA%\\NameChecker (or ~/.namechecker)."""
import json
import os
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get("APPDATA")
    d = Path(base) / "NameChecker" if base else Path.home() / ".namechecker"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load() -> dict:
    try:
        return json.loads((data_dir() / "settings.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(data: dict) -> None:
    try:
        (data_dir() / "settings.json").write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass
