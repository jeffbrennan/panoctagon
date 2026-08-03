from __future__ import annotations

from pathlib import Path

BOXING_DATA_DIR = Path(__file__).parents[2] / "data" / "raw" / "boxing"


def schedule_path() -> Path:
    return BOXING_DATA_DIR / "schedule.html"


def events_dir() -> Path:
    return BOXING_DATA_DIR / "events"


def fighters_dir() -> Path:
    return BOXING_DATA_DIR / "fighters"
