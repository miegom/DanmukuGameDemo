"""Game over scene with score display and return transition."""

from __future__ import annotations

from typing import Any

import pygame

from core.resource_mgr import ResourceManager
from scenes.base_scene import BaseScene


class GameOverScene(BaseScene):
    """Display final score and return to title on key press."""

    def __init__(self, context: dict[str, Any]) -> None:
        """Initialize UI state for the game over screen."""
        super().__init__(context)
        self._ready_for_input: bool = False
        self._enter_elapsed: float = 0.0
        self._title_font = ResourceManager.get_ui_font("gameover_title", 80)
        self._info_font = ResourceManager.get_ui_font("gameover_info", 36)

    def process_input(
        self,
        events: list[pygame.event.Event],
        keys: pygame.key.ScancodeWrapper,
    ) -> None:
        """Return to title scene when any key is pressed."""
        if not self._ready_for_input and not any(keys[i] for i in range(len(keys))):
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
        width, height = screen.get_size()
        screen.fill((18, 4, 10))

        score_value = int(self.context.get("score", 0))

        title_surface = self._title_font.render("游戏结束", True, (255, 110, 120))
        score_surface = self._info_font.render(
            f"得分: {score_value}",
            True,
            (240, 230, 230),
        )
        hint_surface = self._info_font.render(
            "按任意键返回标题",
            True,
            (230, 230, 255),
        )

        screen.blit(title_surface, title_surface.get_rect(center=(width // 2, height // 2 - 60)))
        screen.blit(score_surface, score_surface.get_rect(center=(width // 2, height // 2 + 8)))
        screen.blit(hint_surface, hint_surface.get_rect(center=(width // 2, height // 2 + 54)))
