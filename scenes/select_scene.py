"""Character and weapon selection scene."""

from __future__ import annotations

from typing import Any

import pygame

from scenes.base_scene import BaseScene


class SelectScene(BaseScene):
    """Minimal selection scene used as transition to gameplay."""

    def __init__(self, context: dict[str, Any]) -> None:
        """Initialize selection scene state."""
        super().__init__(context)
        self._ready_for_input: bool = False
        self._enter_elapsed: float = 0.0

    def process_input(
        self,
        events: list[pygame.event.Event],
        keys: pygame.key.ScancodeWrapper,
    ) -> None:
        """Switch to gameplay scene on any key press."""
        if not self._ready_for_input and not any(keys):
            self._ready_for_input = True
        if not self._ready_for_input:
            return
        for event in events:
            if event.type == pygame.KEYDOWN:
                from scenes.gameplay_scene import GameplayScene

                self.switch_to(GameplayScene)
                return

    def update(self, dt: float) -> None:
        """Update selection state."""
        if dt <= 0.0:
            return
        self._enter_elapsed += dt
        if not self._ready_for_input and self._enter_elapsed >= 0.2:
            self._ready_for_input = True

    def draw(self, screen: pygame.Surface) -> None:
        """Render a simple placeholder selection UI."""
        if not pygame.font.get_init():
            pygame.font.init()

        width, height = screen.get_size()
        screen.fill((12, 14, 28))
        title_font = pygame.font.Font(None, 56)
        hint_font = pygame.font.Font(None, 32)

        title_surface = title_font.render("SELECT LOADOUT", True, (255, 220, 180))
        hint_surface = hint_font.render("Press Any Key to Start", True, (220, 230, 255))

        screen.blit(title_surface, title_surface.get_rect(center=(width // 2, height // 2 - 30)))
        screen.blit(hint_surface, hint_surface.get_rect(center=(width // 2, height // 2 + 24)))

