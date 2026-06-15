"""Persistent user preferences (headline window, UI language).

Stored as JSON under macOS Application Support so it survives restarts and never
pollutes the source tree or a packaged .app bundle (which is read-only). Reads
and writes are best-effort: a missing or corrupt file simply yields defaults.
"""

from __future__ import annotations

import json
import os

PATH = os.path.expanduser("~/Library/Application Support/AI Usage/config.json")


def load() -> dict:
    try:
        with open(PATH) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(config: dict) -> None:
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w") as f:
            json.dump(config, f, indent=2)
    except OSError:
        pass
