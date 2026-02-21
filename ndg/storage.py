"""JSON storage helpers — save and load collected data."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def save_json(data: Any, path: str | Path) -> Path:
    """Write *data* to a JSON file (pretty-printed)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    log.info("Saved JSON → %s", path)
    return path


def load_json(path: str | Path) -> Any:
    """Read and return data from a JSON file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
