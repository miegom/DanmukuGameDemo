"""Dedicated integration-test scene for newly added gameplay systems."""

from __future__ import annotations

from typing import Any

import pygame

from logic.entity import ExpOrb
from logic.level_system import WaveManager
from scenes.gameplay_scene import GameplayScene


class FeatureTestScene(GameplayScene):
    """Gameplay variant that stress-tests waves, pickups, and level-up flow."""

    def __init__(self, context: dict[str, Any]) -> None:
        """Initialize gameplay and attach wave/exp test drivers."""
        super().__init__(context)

        self.enemies.clear()
        self.exp_orbs.clear()

        self._wave_manager = WaveManager(random_seed=int(context.get("seed", 20260324)))
        self.context["wave_manager"] = self._wave_manager

        self._orb_spawn_timer: float = 0.0
        self._orb_spawn_interval: float = 1.25
        self._orb_value: int = 55

    def process_input(
        self,
        events: list[pygame.event.Event],
        keys: pygame.key.ScancodeWrapper,
    ) -> None:
        """Keep movement controls and add manual level-up hotkey for testing."""
        super().process_input(events, keys)
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F5:
                self.player.gain_exp(self.player.level * 100)

    def update(self, dt: float) -> None:
        """Inject extra orb drops, then run normal gameplay update."""
        if dt <= 0.0:
            return

        self._orb_spawn_timer += dt
        if self._orb_spawn_timer >= self._orb_spawn_interval:
            self._orb_spawn_timer -= self._orb_spawn_interval
            self.exp_orbs.append(ExpOrb(x=self.player.x + 18.0, y=self.player.y + 6.0, value=self._orb_value))

        super().update(dt)
