"""Standardized scene interface for the game state machine."""

from __future__ import annotations

from typing import Any

import pygame


class BaseScene:
    """Base scene contract used by all concrete scene implementations.

    Subclasses are expected to override input, update, and draw methods.
    """

    def __init__(self, context: dict[str, Any]) -> None:
        """Store shared context and initialize transition target.

        Args:
            context: Mutable dictionary shared across scenes.
        """
        self.context: dict[str, Any] = context
        self.next_scene_class: type[BaseScene] | None = None
        self.next_scene_instance: BaseScene | None = None

    def process_input(
        self,
        events: list[pygame.event.Event],
        keys: pygame.key.ScancodeWrapper,
    ) -> None:
        """Handle input events for the current frame."""
        del events, keys
        raise NotImplementedError("Scene must implement process_input().")

    def update(self, dt: float) -> None:
        """Advance simulation state by ``dt`` seconds."""
        del dt
        raise NotImplementedError("Scene must implement update().")

    def draw(self, screen: pygame.Surface) -> None:
        """Render the scene to the provided screen surface."""
        del screen
        raise NotImplementedError("Scene must implement draw().")

    def switch_to(self, scene_class: type[BaseScene]) -> None:
        """Request transition to another scene class."""
        self.next_scene_instance = None
        self.next_scene_class = scene_class

    def switch_to_instance(self, scene_instance: BaseScene) -> None:
        """Request transition to an existing scene instance."""
        self.next_scene_class = None
        self.next_scene_instance = scene_instance

