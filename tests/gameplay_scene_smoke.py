"""Smoke test for GameplayScene update/draw and collision transition."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pygame

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scenes.gameover_scene import GameOverScene
from scenes.gameplay_scene import GameplayScene


def run_smoke_test() -> None:
    """Run a headless gameplay tick loop and assert transition on collision."""
    pygame.init()
    screen = pygame.Surface((960, 540))

    scene = GameplayScene(context={"screen_width": 960, "screen_height": 540, "score": 0})

    # Warm up regular update/draw path.
    for _ in range(20):
        scene.process_input([], pygame.key.get_pressed())
        scene.update(1.0 / 60.0)
        scene.draw(screen)

    # Advance beyond collision grace period, then force a direct hit.
    while scene.time_value < scene.collision_grace_seconds + (1.0 / 60.0):
        scene.update(1.0 / 60.0)

    # Wait until wave system has spawned at least one enemy.
    for _ in range(240):
        if scene.enemies:
            break
        scene.update(1.0 / 60.0)
    assert scene.enemies, "Expected at least one spawned enemy from wave system."

    # Force one enemy bullet onto player position to verify collision switch.
    enemy_pool = scene.enemies[0].danmaku.pool
    enemy_pool.active_count = 1
    enemy_pool.x[0] = np.float32(scene.player.x)
    enemy_pool.y[0] = np.float32(scene.player.y)
    enemy_pool.vx[0] = np.float32(0.0)
    enemy_pool.vy[0] = np.float32(0.0)

    scene.update(1.0 / 60.0)

    assert scene.next_scene_class is GameOverScene
    assert int(scene.context.get("score", -1)) >= 0

    pygame.quit()
    print("gameplay_scene_smoke_ok")


if __name__ == "__main__":
    run_smoke_test()

