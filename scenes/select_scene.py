"""Character selection scene."""

from __future__ import annotations

from typing import Any

import pygame

from core.resource_mgr import ResourceManager
from logic.character_system import load_character_profiles
from scenes.base_scene import BaseScene


class SelectScene(BaseScene):
    """Character selection scene for choosing Reimu or Morisa."""

    def __init__(self, context: dict[str, Any]) -> None:
        """Initialize selection scene state."""
        super().__init__(context)
        self._ready_for_input: bool = False
        self._enter_elapsed: float = 0.0
        self._selected_index: int = 0
        self._character_order: list[str] = ["reimu", "morisa"]

        if not pygame.font.get_init():
            pygame.font.init()
        self._title_font = ResourceManager.get_ui_font("select_title", 56)
        self._hint_font = ResourceManager.get_ui_font("select_hint", 30)
        self._name_font = ResourceManager.get_ui_font("select_name", 44)
        self._desc_font = ResourceManager.get_ui_font("select_desc", 28)

        ui_config = ResourceManager.load_json("assets/data/ui.json")
        text_map = ui_config.get("texts", {}) if isinstance(ui_config, dict) else {}
        if not isinstance(text_map, dict):
            text_map = {}
        self._title_text = str(text_map.get("select_title", "请选择角色"))
        self._hint_text = str(text_map.get("select_hint", "左右/AD切换，回车确认"))

        profiles = load_character_profiles()
        self._character_data: list[dict[str, Any]] = []
        for char_id in self._character_order:
            profile = profiles.get(char_id)
            if profile is None:
                continue
            description_key = "select_reimu" if char_id == "reimu" else "select_morisa"
            self._character_data.append(
                {
                    "id": profile.char_id,
                    "name": profile.display_name,
                    "desc": str(text_map.get(description_key, profile.display_name)),
                    "outer": profile.icon_outer_color,
                    "inner": profile.icon_inner_color,
                }
            )

        if not self._character_data:
            self._character_data = [
                {
                    "id": "reimu",
                    "name": "灵梦",
                    "desc": "灵梦：奇数狙击弹 + 阴阳玉符卡",
                    "outer": (220, 50, 70),
                    "inner": (255, 255, 255),
                }
            ]

    def process_input(
        self,
        events: list[pygame.event.Event],
        keys: pygame.key.ScancodeWrapper,
    ) -> None:
        """Handle character navigation and confirm action."""
        if not self._ready_for_input and not any(keys[i] for i in range(len(keys))):
            self._ready_for_input = True
        if not self._ready_for_input:
            return

        for event in events:
            if event.type != pygame.KEYDOWN:
                continue

            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._selected_index = (self._selected_index - 1) % len(self._character_data)
                continue

            if event.key in (pygame.K_RIGHT, pygame.K_d):
                self._selected_index = (self._selected_index + 1) % len(self._character_data)
                continue

            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                from scenes.gameplay_scene import GameplayScene

                selected = self._character_data[self._selected_index]
                self.context["selected_character_id"] = selected["id"]
                self.switch_to(GameplayScene)
                return

    def update(self, dt: float) -> None:
        """Update selection scene readiness state."""
        if dt <= 0.0:
            return
        self._enter_elapsed += dt
        if not self._ready_for_input and self._enter_elapsed >= 0.2:
            self._ready_for_input = True

    def draw(self, screen: pygame.Surface) -> None:
        """Render selectable character cards."""
        width, height = screen.get_size()
        screen.fill((12, 14, 28))

        title_surface = self._title_font.render(self._title_text, True, (255, 220, 180))
        hint_surface = self._hint_font.render(self._hint_text, True, (220, 230, 255))
        screen.blit(title_surface, title_surface.get_rect(center=(width // 2, 90)))
        screen.blit(hint_surface, hint_surface.get_rect(center=(width // 2, height - 48)))

        card_width = 360
        card_height = 260
        gap = 40
        total_width = card_width * len(self._character_data) + gap * (len(self._character_data) - 1)
        left = (width - total_width) // 2
        top = (height - card_height) // 2

        for index, data in enumerate(self._character_data):
            rect = pygame.Rect(left + index * (card_width + gap), top, card_width, card_height)
            selected = index == self._selected_index
            bg_color = (62, 56, 108) if selected else (42, 36, 82)
            border = (245, 225, 170) if selected else (140, 136, 190)

            pygame.draw.rect(screen, bg_color, rect, border_radius=12)
            pygame.draw.rect(screen, border, rect, width=3, border_radius=12)

            cx = rect.centerx
            cy = rect.top + 80
            pygame.draw.circle(screen, data["outer"], (cx, cy), 38)
            self._draw_heart(screen, (cx, cy), data["inner"])

            name_surface = self._name_font.render(str(data["name"]), True, (246, 240, 255))
            desc_surface = self._desc_font.render(str(data["desc"]), True, (212, 214, 244))
            screen.blit(name_surface, name_surface.get_rect(center=(cx, rect.top + 150)))
            screen.blit(desc_surface, desc_surface.get_rect(center=(cx, rect.top + 194)))

    def _draw_heart(self, screen: pygame.Surface, center: tuple[int, int], color: tuple[int, int, int]) -> None:
        """Draw a simple heart placeholder inside character icon."""
        x_pos, y_pos = center
        pygame.draw.circle(screen, color, (x_pos - 10, y_pos - 8), 9)
        pygame.draw.circle(screen, color, (x_pos + 10, y_pos - 8), 9)
        points = [(x_pos - 20, y_pos - 2), (x_pos + 20, y_pos - 2), (x_pos, y_pos + 20)]
        pygame.draw.polygon(screen, color, points)
