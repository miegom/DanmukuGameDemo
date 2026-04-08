"""Title scene rendering and input transition logic."""

from __future__ import annotations

from typing import Any

import numpy as np
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
        self._dev_code: str = "devmode"
        self._dev_buffer: str = ""
        self._dev_notice_timer: float = 0.0
        self._dev_mode_enabled: bool = bool(self.context.get("dev_mode", False))

        ui_config = ResourceManager.load_json("assets/data/ui.json")
        text_map = ui_config.get("texts", {}) if isinstance(ui_config, dict) else {}
        if not isinstance(text_map, dict):
            text_map = {}

        self._title_text = str(text_map.get("title", "东方生存弹幕"))
        self._prompt_text = str(text_map.get("title_prompt", "按回车开始（输入 devmode 开启开发模式）"))
        self._devmode_hint_text = str(text_map.get("title_devmode_hint", "开发模式已启用"))
        self._title_font: pygame.font.Font = ResourceManager.get_ui_font("title", 64)
        self._prompt_font: pygame.font.Font = ResourceManager.get_ui_font("title_prompt", 28)

    def process_input(
        self,
        events: list[pygame.event.Event],
        keys: pygame.key.ScancodeWrapper,
    ) -> None:
        """Handle title input and optional developer mode activation code."""
        del keys
        if not self._ready_for_input:
            return
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_BACKSPACE:
                self._dev_buffer = self._dev_buffer[:-1]
                continue

            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                from scenes.select_scene import SelectScene

                self.switch_to(SelectScene)
                return

            # Record typed code in a small rolling buffer for hidden dev mode entry.
            if event.unicode and event.unicode.isprintable():
                self._dev_buffer = (self._dev_buffer + event.unicode.lower())[-24:]
                if self._dev_buffer.endswith(self._dev_code):
                    self.context["dev_mode"] = True
                    self._dev_mode_enabled = True
                    self._dev_notice_timer = 2.4
                    self._dev_buffer = ""

    def update(self, dt: float) -> None:
        """Update blink phase for the start prompt."""
        if dt <= 0.0:
            return
        self._enter_elapsed += dt
        if not self._ready_for_input and self._enter_elapsed >= 0.2:
            self._ready_for_input = True
        self._dev_notice_timer = max(0.0, self._dev_notice_timer - dt)
        self._blink_timer += dt
        if self._blink_timer >= 0.5:
            self._blink_timer -= 0.5
            self._prompt_visible = not self._prompt_visible

    def draw(self, screen: pygame.Surface) -> None:
        """Render centered title and blinking start message."""
        width, height = screen.get_size()
        screen.fill((10, 12, 26))

        title_surface = self._title_font.render(self._title_text, True, (255, 220, 220))
        title_rect = title_surface.get_rect(center=(width // 2, height // 2 - 70))
        screen.blit(title_surface, title_rect)

        if self._prompt_visible:
            prompt_surface = self._prompt_font.render(
                self._prompt_text,
                True,
                (220, 235, 255),
            )
            prompt_rect = prompt_surface.get_rect(center=(width // 2, height // 2 + 18))
            screen.blit(prompt_surface, prompt_rect)

        if self._dev_mode_enabled and (self._dev_notice_timer > 0.0 or np.sin(self._enter_elapsed * 6.0) > 0.0):
            notice_surface = self._prompt_font.render(self._devmode_hint_text, True, (210, 170, 255))
            screen.blit(notice_surface, notice_surface.get_rect(center=(width // 2, height // 2 + 60)))

