"""Highscore save/load utilities with defensive fallback behavior."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.logger import logger
from core.resource_mgr import ResourceManager


HIGHSCORE_PATH = Path("assets/data/highscore.json")


def _parse_highscore(payload: dict[str, Any]) -> int:
    """Parse and sanitize highscore value from JSON payload."""
    value = payload.get("highscore", 0)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def load_highscore() -> int:
    """Load highscore from assets JSON file with safe fallback."""
    payload = ResourceManager.load_json(str(HIGHSCORE_PATH))
    if not isinstance(payload, dict):
        return 0
    return _parse_highscore(payload)


def save_highscore_if_needed(score: int) -> int:
    """Persist highscore when current score beats recorded score."""
    current_score = max(0, int(score))
    previous_high = load_highscore()
    new_high = max(previous_high, current_score)
    if new_high <= previous_high:
        return previous_high

    try:
        HIGHSCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with HIGHSCORE_PATH.open("w", encoding="utf-8") as file_obj:
            json.dump({"highscore": new_high}, file_obj, ensure_ascii=False, indent=2)
        logger.info("Highscore updated: %d", new_high)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        logger.error("Failed to save highscore '%s': %s", HIGHSCORE_PATH, exc)
        return previous_high

    return new_high

