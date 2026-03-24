"""Smoke test for feature-test scene integration behavior."""

from __future__ import annotations

import sys
from pathlib import Path

import pygame

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scenes.feature_test_scene import FeatureTestScene


def run_smoke_test() -> None:
    """Ensure feature-test scene spawns enemies and keeps running state."""
    pygame.init()
    screen = pygame.Surface((1280, 720))

    scene = FeatureTestScene({"screen_width": 1280, "screen_height": 720, "score": 0})

    for _ in range(220):
        scene.process_input([], pygame.key.get_pressed())
        scene.update(1.0 / 60.0)
        scene.draw(screen)

    assert "wave_manager" in scene.context
    assert len(scene.enemies) >= 1
    assert scene.player.level >= 1

    pygame.quit()
    print(f"feature_test_scene_smoke_ok enemies={len(scene.enemies)} level={scene.player.level}")


if __name__ == "__main__":
    run_smoke_test()

