"""Wave-based enemy spawning system for gameplay progression."""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import cos, sin, tau
from typing import Any

from core.logger import logger
from core.resource_mgr import ResourceManager
from logic.danmaku_system import DanmakuGroup, DiscreteShape, EmissionOperator, LinearMotion
from logic.entity import Enemy


@dataclass(frozen=True, slots=True)
class WaveDefinition:
    """Configuration for a single enemy wave segment."""

    duration: float
    spawn_interval: float
    enemy_type: str
    count: int


class WaveManager:
    """Manage wave timing and off-screen enemy spawning."""

    _DEFAULT_SPAWN_RADIUS = 820.0
    _MIN_SAFE_SPAWN_RADIUS = 800.0
    _DEFAULT_MAX_ACTIVE_ENEMIES = 8
    _FULL_CAP_SPAWN_PRESSURE = 0.2
    _DEFAULT_DATA_PATH = "assets/data/waves.json"
    _ENEMY_PRESETS: dict[str, dict[str, float | int]] = {
        "fairy_basic": {
            "hp": 20,
            "radius": 12.0,
            "fire_rate": 1.1,
            "bullet_speed": 95.0,
            "spread": 0.85,
            "fan_count": 5,
        },
        "fairy_fast": {
            "hp": 14,
            "radius": 10.0,
            "fire_rate": 1.6,
            "bullet_speed": 120.0,
            "spread": 0.65,
            "fan_count": 5,
        },
        "fairy_sniper": {
            "hp": 24,
            "radius": 13.0,
            "fire_rate": 0.9,
            "bullet_speed": 150.0,
            "spread": 0.35,
            "fan_count": 3,
        },
    }

    def __init__(
        self,
        data_path: str = _DEFAULT_DATA_PATH,
        spawn_radius: float | None = None,
        random_seed: int | None = None,
    ) -> None:
        """Load wave definitions and initialize internal timers.

        Args:
            data_path: Path to wave configuration JSON.
            spawn_radius: Optional override for enemy spawn ring radius.
            random_seed: Optional seed for deterministic spawn patterns.
        """
        payload = ResourceManager.load_json(data_path)
        waves_raw = payload.get("waves", []) if isinstance(payload, dict) else []

        self._waves: list[WaveDefinition] = self._parse_waves(waves_raw)
        self._loop_waves: bool = bool(payload.get("loop_waves", True))

        radius_from_data = float(payload.get("spawn_radius", self._DEFAULT_SPAWN_RADIUS))
        radius_candidate = float(spawn_radius) if spawn_radius is not None else radius_from_data
        self._spawn_radius: float = max(radius_candidate, self._MIN_SAFE_SPAWN_RADIUS)

        self._rng = random.Random(random_seed)
        self._wave_index: int = 0
        self._wave_elapsed: float = 0.0
        self._spawn_elapsed: float = 0.0

        if not self._waves:
            logger.warning(
                "No valid waves found in '%s'. Using default infinite fallback wave.",
                data_path,
            )
            self._waves = [
                WaveDefinition(
                    duration=1.0e12,
                    spawn_interval=1.2,
                    enemy_type="fairy_basic",
                    count=2,
                )
            ]

        logger.info(
            "WaveManager initialized: waves=%d, spawn_radius=%.1f, loop=%s",
            len(self._waves),
            self._spawn_radius,
            self._loop_waves,
        )
        self._log_wave_started()

    @property
    def current_wave_index(self) -> int:
        """Return current wave index (zero-based)."""
        return self._wave_index

    @property
    def waves(self) -> list[WaveDefinition]:
        """Return parsed wave definitions."""
        return self._waves

    @property
    def wave_count(self) -> int:
        """Return total configured wave count."""
        return len(self._waves)

    def update(self, dt: float, player_x: float, player_y: float) -> list[Enemy]:
        """Advance wave timers and spawn enemies around the player.

        Enemies are spawned on a ring centered at the player with radius
        ``spawn_radius``, which keeps them outside the immediate play area.

        Args:
            dt: Delta time in seconds.
            player_x: Player world x coordinate.
            player_y: Player world y coordinate.

        Returns:
            A list of newly spawned enemies for this update step.
        """
        return self.update_with_cap(
            dt=dt,
            player_x=player_x,
            player_y=player_y,
            current_enemy_count=0,
            max_active_enemies=self._DEFAULT_MAX_ACTIVE_ENEMIES,
        )

    def update_with_cap(
        self,
        dt: float,
        player_x: float,
        player_y: float,
        current_enemy_count: int,
        max_active_enemies: int = _DEFAULT_MAX_ACTIVE_ENEMIES,
    ) -> list[Enemy]:
        """Advance waves with active-enemy cap and full-cap spawn slowdown.

        When enemy count reaches cap, spawn timer advances slower so refill
        pressure is reduced and difficulty spikes are softened.
        """
        if dt <= 0.0 or not self._waves:
            return []

        safe_cap = max(1, int(max_active_enemies))
        enemy_count = max(0, int(current_enemy_count))
        available_slots = max(0, safe_cap - enemy_count)

        self._wave_elapsed += dt
        spawn_pressure = 1.0 if available_slots > 0 else self._FULL_CAP_SPAWN_PRESSURE
        self._spawn_elapsed += dt * spawn_pressure
        self._advance_wave_if_needed()

        active_wave = self._waves[self._wave_index]
        if active_wave.spawn_interval <= 0.0:
            logger.error("Invalid spawn_interval in wave %d", self._wave_index)
            return []

        spawn_events = int(self._spawn_elapsed // active_wave.spawn_interval)
        if spawn_events <= 0:
            return []

        self._spawn_elapsed -= spawn_events * active_wave.spawn_interval

        spawned_enemies: list[Enemy] = []
        for _ in range(spawn_events):
            if available_slots <= 0:
                break

            batch = self._spawn_wave_batch(
                active_wave,
                player_x=player_x,
                player_y=player_y,
            )
            if len(batch) > available_slots:
                batch = batch[:available_slots]

            available_slots -= len(batch)
            spawned_enemies.extend(batch)

        if not spawned_enemies:
            return []

        logger.info(
            "Spawned %d enemies in wave %d (%s), active=%d/%d",
            len(spawned_enemies),
            self._wave_index + 1,
            active_wave.enemy_type,
            enemy_count + len(spawned_enemies),
            safe_cap,
        )
        return spawned_enemies

    def _advance_wave_if_needed(self) -> None:
        """Switch to next wave once current wave duration has elapsed."""
        while self._waves:
            current = self._waves[self._wave_index]
            if current.duration <= 0.0 or self._wave_elapsed < current.duration:
                break

            self._wave_elapsed -= current.duration
            self._spawn_elapsed = 0.0

            if self._wave_index + 1 < len(self._waves):
                self._wave_index += 1
                self._log_wave_started()
                continue

            if self._loop_waves:
                self._wave_index = 0
                self._log_wave_started()
            else:
                self._wave_index = len(self._waves) - 1
                self._wave_elapsed = min(self._wave_elapsed, current.duration)
                break

    def _log_wave_started(self) -> None:
        """Emit an info log when the active wave index changes."""
        active_wave = self._waves[self._wave_index]
        logger.info(
            "Wave %d started: duration=%.2fs, interval=%.2fs, type=%s, count=%d",
            self._wave_index + 1,
            active_wave.duration,
            active_wave.spawn_interval,
            active_wave.enemy_type,
            active_wave.count,
        )

    def _spawn_wave_batch(
        self,
        wave: WaveDefinition,
        player_x: float,
        player_y: float,
    ) -> list[Enemy]:
        """Spawn one configured batch on a random ring around the player."""
        enemies: list[Enemy] = []
        for _ in range(wave.count):
            angle = self._rng.random() * tau
            spawn_x = player_x + (self._spawn_radius * cos(angle))
            spawn_y = player_y + (self._spawn_radius * sin(angle))
            enemies.append(self._build_enemy(wave.enemy_type, spawn_x, spawn_y))
        return enemies

    def _build_enemy(self, enemy_type: str, x_pos: float, y_pos: float) -> Enemy:
        """Instantiate an enemy from preset stats and danmaku profile."""
        preset = self._ENEMY_PRESETS.get(enemy_type, self._ENEMY_PRESETS["fairy_basic"])

        fan_count = int(preset["fan_count"])
        spread = float(preset["spread"])
        bullet_speed = float(preset["bullet_speed"])
        fire_rate = float(preset["fire_rate"])

        danmaku = DanmakuGroup(
            shape=DiscreteShape(count=fan_count, spread=spread),
            emission=EmissionOperator(
                fire_rate=fire_rate,
                speed=bullet_speed,
                spin_speed=0.0,
            ),
            motions=[LinearMotion()],
            max_bullets=2048,
            bounds=(-2000.0, 2000.0, -2000.0, 2000.0),
        )

        return Enemy(
            x=x_pos,
            y=y_pos,
            hp=int(preset["hp"]),
            radius=float(preset["radius"]),
            danmaku=danmaku,
        )

    @staticmethod
    def _parse_waves(raw_waves: Any) -> list[WaveDefinition]:
        """Validate and normalize wave entries loaded from JSON."""
        if not isinstance(raw_waves, list):
            return []

        waves: list[WaveDefinition] = []
        for raw in raw_waves:
            if not isinstance(raw, dict):
                continue

            try:
                wave = WaveDefinition(
                    duration=float(raw["duration"]),
                    spawn_interval=float(raw["spawn_interval"]),
                    enemy_type=str(raw["enemy_type"]),
                    count=max(1, int(raw["count"])),
                )
            except (KeyError, TypeError, ValueError):
                continue

            waves.append(wave)

        return waves


