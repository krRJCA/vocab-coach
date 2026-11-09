"""Leitner spaced repetition.

Every phrase sits in a box from 1 to 5. A correct answer moves it up one
box (longer wait before the next review); a wrong answer sends it back to
box 1 (review tomorrow).
"""

import json
from datetime import date, timedelta
from pathlib import Path

INTERVALS = {1: 1, 2: 2, 3: 4, 4: 7, 5: 15}  # box -> days until next review
MAX_BOX = max(INTERVALS)


def load(path):
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save(progress, path):
    Path(path).write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add(progress, chunk_id, today=None):
    """Put a new phrase in box 1, due today. Known phrases are left alone."""
    today = today or date.today()
    progress.setdefault(
        chunk_id, {"box": 1, "due": today.isoformat(), "history": []}
    )


def record(progress, chunk_id, correct, today=None):
    """Move a phrase between boxes and set its next review date."""
    today = today or date.today()
    add(progress, chunk_id, today)
    item = progress[chunk_id]
    item["box"] = min(item["box"] + 1, MAX_BOX) if correct else 1
    item["due"] = (today + timedelta(days=INTERVALS[item["box"]])).isoformat()
    item["history"].append({"date": today.isoformat(), "correct": correct})


def due_items(progress, today=None):
    """IDs of phrases whose review date is today or earlier."""
    today = (today or date.today()).isoformat()
    return [chunk_id for chunk_id, item in progress.items() if item["due"] <= today]
