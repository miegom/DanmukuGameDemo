"""Application entrypoint and scene-state machine loop."""

from __future__ import annotations

import sys
from typing import Any, cast

import pygame

from core.logger import logger
from scenes.base_scene import BaseScene
from scenes.title_scene import TitleScene

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
WINDOW_TITLE = "东方生存弹幕"
FEATURE_TEST_FLAG = "--feature-test"


def _get_next_scene_class(scene: BaseScene) -> type[BaseScene] | None:
    """Read pending transition target from scene instance.

    Supports both ``next_scene`` and ``next_scene_class`` for compatibility.
    """
    next_scene = getattr(scene, "next_scene", None)
    if next_scene is None:
        next_scene = getattr(scene, "next_scene_class", None)

    if isinstance(next_scene, type):
        return cast(type[BaseScene], next_scene)
    return None


def _get_next_scene_instance(scene: BaseScene) -> BaseScene | None:
    """Read pending transition scene instance from scene object."""
    next_scene_instance = getattr(scene, "next_scene_instance", None)
    if isinstance(next_scene_instance, BaseScene):
        return next_scene_instance
    return None


def main() -> None:
    """Run the game loop and dispatch scene lifecycle calls."""
    pygame.init()

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    game_context: dict[str, Any] = {
        "score": 0,
        "weapons": {},
        "screen_width": WINDOW_WIDTH,
        "screen_height": WINDOW_HEIGHT,
    }
    if FEATURE_TEST_FLAG in sys.argv:
        from scenes.feature_test_scene import FeatureTestScene

        logger.info("Boot mode: feature test scene")
        current_scene = FeatureTestScene(game_context)
    else:
        current_scene = TitleScene(game_context)
    running = True

    try:
        while running:
            dt = clock.tick(60) / 1000.0
            events = pygame.event.get()

            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                    break

            if not running:
                continue

            keys = pygame.key.get_pressed()
            current_scene.process_input(events, keys)
            current_scene.update(dt)
            current_scene.draw(screen)

            next_scene_instance = _get_next_scene_instance(current_scene)
            if next_scene_instance is not None:
                logger.info(
                    "Scene switch: %s -> %s",
                    current_scene.__class__.__name__,
                    next_scene_instance.__class__.__name__,
                )
                current_scene = next_scene_instance
                current_scene.next_scene_class = None
                current_scene.next_scene_instance = None
                pygame.display.flip()
                continue

            next_scene_class = _get_next_scene_class(current_scene)
            if next_scene_class is not None:
                logger.info(
                    "Scene switch: %s -> %s",
                    current_scene.__class__.__name__,
                    next_scene_class.__name__,
                )
                current_scene = next_scene_class(game_context)
                current_scene.next_scene_class = None
                current_scene.next_scene_instance = None

            pygame.display.flip()
    except Exception:
        logger.exception("Unhandled exception in main loop")
        raise
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
