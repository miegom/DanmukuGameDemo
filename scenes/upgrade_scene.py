"""Intermission 3-choice upgrade scene."""

from __future__ import annotations

from typing import Any

import pygame

from core.logger import logger
from core.resource_mgr import ResourceManager
from logic.entity import Player
from logic.roguelite_system import UpgradeManager
from scenes.base_scene import BaseScene


class UpgradeScene(BaseScene):
    """Three-choice roguelite upgrade scene."""

    def __init__(self, context: dict[str, Any]) -> None:
        """Initialize selection state and fetch upgrade candidates."""
        super().__init__(context)
        self._ready_for_input: bool = False
        self._enter_elapsed: float = 0.0
        self._option_rects: list[pygame.Rect] = []
        self._overlay_surface: pygame.Surface | None = None
        self._title_font = ResourceManager.get_ui_font("upgrade_title", 62)
        self._text_font = ResourceManager.get_ui_font("upgrade_text", 32)
        self._hint_font = ResourceManager.get_ui_font("upgrade_hint", 28)

        manager = self.context.get("upgrade_manager")
        if isinstance(manager, UpgradeManager):
            self._upgrade_manager = manager
        else:
            self._upgrade_manager = UpgradeManager()
            self.context["upgrade_manager"] = self._upgrade_manager

        player_for_choices = self.context.get("player")
        if isinstance(player_for_choices, Player):
            self._choices = self._upgrade_manager.get_random_choices_for_player(player_for_choices, 3)
        else:
            self._choices = self._upgrade_manager.get_random_choices(3)

        gameplay_scene = self.context.get("previous_gameplay_scene")
        if isinstance(gameplay_scene, BaseScene):
            self._previous_gameplay_scene: BaseScene | None = gameplay_scene
        else:
            self._previous_gameplay_scene = None

    def process_input(
        self,
        events: list[pygame.event.Event],
        keys: pygame.key.ScancodeWrapper,
    ) -> None:
        """Handle mouse or keyboard selection and resume gameplay."""
        if not self._ready_for_input and not any(keys[i] for i in range(len(keys))):
            self._ready_for_input = True
        if not self._ready_for_input:
            return

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._select_by_position(event.pos)
                return

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    self._apply_choice(0)
                    return
                if event.key == pygame.K_2:
                    self._apply_choice(1)
                    return
                if event.key == pygame.K_3:
                    self._apply_choice(2)
                    return

    def update(self, dt: float) -> None:
        """Update scene readiness timer."""
        if dt <= 0.0:
            return
        self._enter_elapsed += dt

    def draw(self, screen: pygame.Surface) -> None:
        """Render dimmed background and centered 3-choice cards."""
        snapshot = self.context.get("gameplay_snapshot")
        if isinstance(snapshot, pygame.Surface):
            screen.blit(snapshot, (0, 0))
        else:
            screen.fill((14, 12, 20))

        width, height = screen.get_size()
        if self._overlay_surface is None or self._overlay_surface.get_size() != (width, height):
            self._overlay_surface = pygame.Surface((width, height), flags=pygame.SRCALPHA)
            self._overlay_surface.fill((0, 0, 0, 180))
        screen.blit(self._overlay_surface, (0, 0))

        title_surface = self._title_font.render("选择一项强化", True, (245, 228, 165))
        screen.blit(title_surface, title_surface.get_rect(center=(width // 2, 120)))

        self._option_rects = self._build_option_rects(width, height, len(self._choices))
        mouse_pos = pygame.mouse.get_pos()

        for index, rect in enumerate(self._option_rects):
            hovered = rect.collidepoint(mouse_pos)
            fill_color = (74, 62, 120) if hovered else (52, 42, 92)
            border_color = (240, 225, 150) if hovered else (176, 164, 220)

            pygame.draw.rect(screen, fill_color, rect, border_radius=10)
            pygame.draw.rect(screen, border_color, rect, width=2, border_radius=10)

            choice = self._choices[index]
            name = str(choice.get("name", f"Option {index + 1}"))
            description = str(choice.get("description", "No description."))
            channel = self._format_channel_tag(choice)

            title_text = self._text_font.render(f"[{index + 1}] {channel} {name}", True, (240, 238, 255))
            desc_text = self._hint_font.render(description, True, (210, 210, 240))
            screen.blit(title_text, title_text.get_rect(midtop=(rect.centerx, rect.top + 16)))
            screen.blit(desc_text, desc_text.get_rect(midtop=(rect.centerx, rect.top + 54)))

        hint_surface = self._hint_font.render("点击卡片或按 1 / 2 / 3", True, (196, 206, 240))
        screen.blit(hint_surface, hint_surface.get_rect(center=(width // 2, height - 58)))

    def _build_option_rects(self, width: int, height: int, count: int) -> list[pygame.Rect]:
        """Build centered option-card rectangles for current choice count."""
        if count <= 0:
            return []

        card_width = 320
        card_height = 130
        gap = 24
        total_width = (count * card_width) + ((count - 1) * gap)
        left = (width - total_width) // 2
        top = (height // 2) - (card_height // 2)

        return [
            pygame.Rect(left + index * (card_width + gap), top, card_width, card_height)
            for index in range(count)
        ]

    def _select_by_position(self, pos: tuple[int, int]) -> None:
        """Apply upgrade corresponding to clicked card position."""
        for index, rect in enumerate(self._option_rects):
            if rect.collidepoint(pos):
                self._apply_choice(index)
                return

    def _apply_choice(self, index: int) -> None:
        """Apply selected upgrade and resume gameplay from saved instance."""
        if index < 0 or index >= len(self._choices):
            return

        player = self.context.get("player")
        if not isinstance(player, Player):
            logger.error("UpgradeScene missing valid context['player']; skip apply.")
            self._resume_gameplay()
            return

        upgrade = self._choices[index]
        self._upgrade_manager.apply_upgrade(upgrade, player)
        self._resume_gameplay()

    def _format_channel_tag(self, choice: dict[str, Any]) -> str:
        """Return display tag for upgrade channel."""
        channel = str(choice.get("attack_channel", "")).strip().lower()
        if channel == "spell":
            return "[符卡]"
        if channel == "basic":
            return "[普攻]"
        if channel == "common":
            return "[通用]"

        param = str(choice.get("param", "")).strip().lower()
        if "_spell_" in param:
            return "[符卡]"
        return "[普攻]"

    def _resume_gameplay(self) -> None:
        """Return to gameplay while preserving existing runtime state."""
        from scenes.gameplay_scene import GameplayScene

        if isinstance(self._previous_gameplay_scene, GameplayScene):
            self._previous_gameplay_scene.next_scene_class = None
            self._previous_gameplay_scene.next_scene_instance = None
            self.switch_to_instance(self._previous_gameplay_scene)
            return

        gameplay_scene = self.context.get("gameplay_scene")
        if isinstance(gameplay_scene, GameplayScene):
            gameplay_scene.next_scene_class = None
            gameplay_scene.next_scene_instance = None
            self.switch_to_instance(gameplay_scene)
            return

        logger.warning("UpgradeScene fallback: previous gameplay scene missing; creating new GameplayScene.")

        self.switch_to(GameplayScene)
