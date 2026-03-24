"""Title scene rendering and input transition logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pygame

from core.resource_mgr import ResourceManager
from scenes.base_scene import BaseScene


class TitleScene(BaseScene):
    """Display title UI and wait for user input to start the game."""

    def __init__(self, context: dict[str, Any]) -> None:
        """Initialize title scene render state."""
        super().__init__(context)
        self._blink_timer: float = 0.0
        self._prompt_visible: bool = True
        self._ready_for_input: bool = False
        self._enter_elapsed: float = 0.0
        font_config = ResourceManager.load_json("assets/data/ui.json")
        self._title_font_path: str = str(font_config.get("title_font", "")).strip()

    def process_input(
        self,
        events: list[pygame.event.Event],
        keys: pygame.key.ScancodeWrapper,
    ) -> None:
        """Switch to select scene on any key press."""
        if not self._ready_for_input and not any(keys):
            self._ready_for_input = True
        if not self._ready_for_input:
            return
        for event in events:
            if event.type == pygame.KEYDOWN:
                from scenes.select_scene import SelectScene

                self.switch_to(SelectScene)
                return

    def update(self, dt: float) -> None:
        """Update blink phase for the start prompt."""
        if dt <= 0.0:
            return
        self._enter_elapsed += dt
        if not self._ready_for_input and self._enter_elapsed >= 0.2:
            self._ready_for_input = True
        self._blink_timer += dt
        if self._blink_timer >= 0.5:
            self._blink_timer -= 0.5
            self._prompt_visible = not self._prompt_visible

    def draw(self, screen: pygame.Surface) -> None:
        """Render centered title and blinking start message."""
        width, height = screen.get_size()
        screen.fill((10, 12, 26))

        title_font = self._load_font(size=64)
        prompt_font = self._load_font(size=28)

        title_surface = title_font.render("TOUHOU SURVIVORS", True, (255, 220, 220))
        title_rect = title_surface.get_rect(center=(width // 2, height // 2 - 70))
        screen.blit(title_surface, title_rect)

        if self._prompt_visible:
            prompt_surface = prompt_font.render(
                "Press Any Key to Start",
                True,
                (220, 235, 255),
            )
            prompt_rect = prompt_surface.get_rect(center=(width // 2, height // 2 + 18))
            screen.blit(prompt_surface, prompt_rect)

    def _load_font(self, size: int) -> pygame.font.Font:
        """Load configured font with fallback to pygame default font."""
        if not pygame.font.get_init():
            pygame.font.init()

        if not self._title_font_path:
            return pygame.font.Font(None, size)

        if not Path(self._title_font_path).exists():
            return pygame.font.Font(None, size)

        try:
            return pygame.font.Font(self._title_font_path, size)
        except Exception:
            return pygame.font.Font(None, size)

