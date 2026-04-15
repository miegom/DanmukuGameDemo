"""Smoke test for highscore save/load behavior."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.save_system import HIGHSCORE_PATH, load_highscore, save_highscore_if_needed


def run_smoke_test() -> None:
    """Validate save/load/update behavior for local highscore file."""
    backup_payload: str | None = None
    if HIGHSCORE_PATH.exists():
        backup_payload = HIGHSCORE_PATH.read_text(encoding="utf-8")

    try:
        HIGHSCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        HIGHSCORE_PATH.write_text('{"highscore": 5}\n', encoding="utf-8")

        assert load_highscore() == 5
        assert save_highscore_if_needed(4) == 5
        assert load_highscore() == 5

        assert save_highscore_if_needed(9) == 9
        payload = json.loads(HIGHSCORE_PATH.read_text(encoding="utf-8"))
        assert int(payload.get("highscore", -1)) == 9

        HIGHSCORE_PATH.write_text('{"highscore": "bad"}\n', encoding="utf-8")
        assert load_highscore() == 0
    finally:
        if backup_payload is None:
            HIGHSCORE_PATH.write_text('{"highscore": 0}\n', encoding="utf-8")
        else:
            HIGHSCORE_PATH.write_text(backup_payload, encoding="utf-8")

    print("highscore_smoke_ok")


if __name__ == "__main__":
    run_smoke_test()

