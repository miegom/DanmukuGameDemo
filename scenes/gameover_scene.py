"""Game over scene with score display and return transition."""

from __future__ import annotations

from typing import Any

import pygame

from scenes.base_scene import BaseScene


class GameOverScene(BaseScene):
    """Display final score and return to title on key press."""

    def __init__(self, context: dict[str, Any]) -> None:
        """Initialize UI state for the game over screen."""
        super().__init__(context)
        self._ready_for_input: bool = False
        self._enter_elapsed: float = 0.0

    def process_input(
        self,
        events: list[pygame.event.Event],
        keys: pygame.key.ScancodeWrapper,
    ) -> None:
        """Return to title scene when any key is pressed."""
        if not self._ready_for_input and not any(keys):
            self._ready_for_input = True
        if not self._ready_for_input:
            return
        for event in events:
            if event.type == pygame.KEYDOWN:
                from scenes.title_scene import TitleScene

                self.switch_to(TitleScene)
                return

    def update(self, dt: float) -> None:
        """Update game over scene state."""
        if dt <= 0.0:
            return
        self._enter_elapsed += dt
        if not self._ready_for_input and self._enter_elapsed >= 0.2:
            self._ready_for_input = True

    def draw(self, screen: pygame.Surface) -> None:
        """Render game over title and final score information."""
        if not pygame.font.get_init():
            pygame.font.init()

        width, height = screen.get_size()
        screen.fill((18, 4, 10))

        title_font = pygame.font.Font(None, 80)
        info_font = pygame.font.Font(None, 36)

        score_value = int(self.context.get("score", 0))

        title_surface = title_font.render("GAME OVER", True, (255, 110, 120))
        score_surface = info_font.render(
            f"Score: {score_value}",
            True,
            (240, 230, 230),
        )
        hint_surface = info_font.render(
            "Press Any Key to Return",
            True,
            (230, 230, 255),
        )

        screen.blit(title_surface, title_surface.get_rect(center=(width // 2, height // 2 - 60)))
        screen.blit(score_surface, score_surface.get_rect(center=(width // 2, height // 2 + 8)))
        screen.blit(hint_surface, hint_surface.get_rect(center=(width // 2, height // 2 + 54)))

