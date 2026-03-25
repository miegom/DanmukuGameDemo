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


@dataclass(frozen=True, slots=True)
class _WeightedEnemyEntry:
    """Weighted candidate enemy entry for one wave range."""

    enemy_type: str
    weight: float


@dataclass(frozen=True, slots=True)
class _WaveEnemyPool:
    """Enemy pool active within a wave-number interval."""

    min_wave: int
    max_wave: int
    entries: list[_WeightedEnemyEntry]


class WaveManager:
    """Manage wave timing and off-screen enemy spawning."""

    _DEFAULT_SPAWN_RADIUS = 820.0
    _MIN_SAFE_SPAWN_RADIUS = 800.0
    _DEFAULT_MAX_ACTIVE_ENEMIES = 8
    _FULL_CAP_SPAWN_PRESSURE = 0.25
    _DEFAULT_DATA_PATH = "assets/data/waves.json"
    _DEFAULT_WAVE_DURATION = 30.0

    def __init__(
        self,
        data_path: str = _DEFAULT_DATA_PATH,
        spawn_radius: float | None = None,
        random_seed: int | None = None,
    ) -> None:
        """Load wave definitions and initialize internal timers."""
        payload = ResourceManager.load_json(data_path)

        self._wave_duration: float = max(5.0, float(payload.get("wave_duration", self._DEFAULT_WAVE_DURATION)))
        radius_from_data = float(payload.get("spawn_radius", self._DEFAULT_SPAWN_RADIUS))
        radius_candidate = float(spawn_radius) if spawn_radius is not None else radius_from_data
        self._spawn_radius: float = max(radius_candidate, self._MIN_SAFE_SPAWN_RADIUS)

        self._enemy_presets = self._parse_enemy_presets(payload.get("enemy_presets", {}))
        self._enemy_pools = self._parse_enemy_pools(payload.get("enemy_pools", []))

        self._rng = random.Random(random_seed)
        self._wave_number: int = 1
        self._wave_elapsed: float = 0.0
        self._spawn_elapsed: float = 0.0
        self._current_wave: WaveDefinition = self._make_wave_definition(self._wave_number)

        # Keep compatibility for HUD/tests expecting a waves list.
        self._waves: list[WaveDefinition] = [self._make_wave_definition(i) for i in range(1, 25)]

        logger.info(
            "WaveManager initialized: wave_duration=%.1fs, spawn_radius=%.1f",
            self._wave_duration,
            self._spawn_radius,
        )
        self._log_wave_started()

    @property
    def current_wave_index(self) -> int:
        """Return current wave index (zero-based)."""
        return max(0, self._wave_number - 1)

    @property
    def current_wave_number(self) -> int:
        """Return current wave number (one-based)."""
        return self._wave_number

    @property
    def waves(self) -> list[WaveDefinition]:
        """Return compatibility wave definitions for HUD display."""
        return self._waves

    @property
    def wave_count(self) -> int:
        """Return total configured compatibility wave count."""
        return len(self._waves)

    @property
    def wave_duration(self) -> float:
        """Return per-wave duration in seconds."""
        return self._wave_duration

    def get_spawn_cap_for_wave(self, wave_number: int) -> int:
        """Compute active-enemy cap based on wave number."""
        wave = max(1, int(wave_number))
        if wave <= 3:
            return 6
        if wave <= 6:
            return 9
        return 9 + (wave - 6)

    def update(self, dt: float, player_x: float, player_y: float) -> list[Enemy]:
        """Advance wave timers and spawn enemies around the player."""
        return self.update_with_cap(
            dt=dt,
            player_x=player_x,
            player_y=player_y,
            current_enemy_count=0,
            max_active_enemies=self.get_spawn_cap_for_wave(self._wave_number),
        )

    def update_with_cap(
        self,
        dt: float,
        player_x: float,
        player_y: float,
        current_enemy_count: int,
        max_active_enemies: int = _DEFAULT_MAX_ACTIVE_ENEMIES,
    ) -> list[Enemy]:
        """Advance waves with active-enemy cap and full-cap spawn slowdown."""
        if dt <= 0.0:
            return []

        wave_cap = self.get_spawn_cap_for_wave(self._wave_number)
        requested_cap = max(1, int(max_active_enemies))
        safe_cap = min(wave_cap, requested_cap)

        enemy_count = max(0, int(current_enemy_count))
        available_slots = max(0, safe_cap - enemy_count)

        self._wave_elapsed += dt
        spawn_pressure = 1.0 if available_slots > 0 else self._FULL_CAP_SPAWN_PRESSURE
        self._spawn_elapsed += dt * spawn_pressure
        self._advance_wave_if_needed()

        active_wave = self._current_wave
        spawn_events = int(self._spawn_elapsed // active_wave.spawn_interval)
        if spawn_events <= 0:
            return []
        self._spawn_elapsed -= spawn_events * active_wave.spawn_interval

        spawned_enemies: list[Enemy] = []
        for _ in range(spawn_events):
            if available_slots <= 0:
                break

            batch = self._spawn_wave_batch(
                wave=active_wave,
                player_x=player_x,
                player_y=player_y,
            )
            if len(batch) > available_slots:
                batch = batch[:available_slots]

            available_slots -= len(batch)
            spawned_enemies.extend(batch)

        if spawned_enemies:
            logger.info(
                "Spawned %d enemies in wave %d, active=%d/%d",
                len(spawned_enemies),
                self._wave_number,
                enemy_count + len(spawned_enemies),
                safe_cap,
            )

        return spawned_enemies

    def _advance_wave_if_needed(self) -> None:
        """Advance to next wave once 30-second segment expires."""
        while self._wave_elapsed >= self._wave_duration:
            self._wave_elapsed -= self._wave_duration
            self._spawn_elapsed = 0.0
            self._wave_number += 1
            self._current_wave = self._make_wave_definition(self._wave_number)
            self._log_wave_started()

    def _make_wave_definition(self, wave_number: int) -> WaveDefinition:
        """Create runtime wave pacing profile from wave number."""
        wave = max(1, int(wave_number))
        if wave <= 2:
            interval = 2.1
            count = 1
        elif wave <= 4:
            interval = 1.7
            count = 1
        elif wave <= 6:
            interval = 1.35
            count = 2
        else:
            interval = max(0.6, 1.25 - (wave - 6) * 0.03)
            count = min(4, 2 + ((wave - 6) // 4))

        return WaveDefinition(
            duration=self._wave_duration,
            spawn_interval=interval,
            enemy_type="mixed_zako",
            count=count,
        )

    def _log_wave_started(self) -> None:
        """Emit an info log when the active wave number changes."""
        logger.info(
            "Wave %d started: duration=%.1fs, interval=%.2fs, batch=%d, cap=%d",
            self._wave_number,
            self._current_wave.duration,
            self._current_wave.spawn_interval,
            self._current_wave.count,
            self.get_spawn_cap_for_wave(self._wave_number),
        )

    def _spawn_wave_batch(self, wave: WaveDefinition, player_x: float, player_y: float) -> list[Enemy]:
        """Spawn one configured batch on a random ring around the player."""
        del wave
        enemies: list[Enemy] = []
        for _ in range(self._current_wave.count):
            enemy_type = self._pick_enemy_type_for_wave(self._wave_number)
            angle = self._rng.random() * tau
            spawn_x = player_x + (self._spawn_radius * cos(angle))
            spawn_y = player_y + (self._spawn_radius * sin(angle))
            enemies.append(self._build_enemy(enemy_type, spawn_x, spawn_y))
        return enemies

    def _pick_enemy_type_for_wave(self, wave_number: int) -> str:
        """Pick one enemy type by weighted pools active in this wave."""
        entries: list[_WeightedEnemyEntry] = []
        for pool in self._enemy_pools:
            if pool.min_wave <= wave_number <= pool.max_wave:
                entries.extend(pool.entries)

        if not entries:
            return "zako_fairy_small"

        total_weight = sum(max(0.0, item.weight) for item in entries)
        if total_weight <= 1.0e-6:
            return entries[0].enemy_type

        threshold = self._rng.random() * total_weight
        running = 0.0
        for item in entries:
            running += max(0.0, item.weight)
            if running >= threshold:
                return item.enemy_type

        return entries[-1].enemy_type

    def _build_enemy(self, enemy_type: str, x_pos: float, y_pos: float) -> Enemy:
        """Instantiate an enemy from preset stats and danmaku profile."""
        preset = self._enemy_presets.get(enemy_type)
        if preset is None:
            preset = self._enemy_presets["zako_fairy_small"]

        danmaku = DanmakuGroup(
            shape=DiscreteShape(
                count=max(1, int(preset.get("burst_fan_count", 3))),
                spread=float(preset.get("burst_spread", 0.2)),
                base_angle=0.0,
            ),
            emission=EmissionOperator(
                fire_rate=0.0,
                speed=float(preset.get("burst_bullet_speed", 150.0)),
                spin_speed=0.0,
            ),
            motions=[LinearMotion()],
            max_bullets=2048,
            bounds=(-4000.0, 4000.0, -3200.0, 3200.0),
            max_lifetime=max(0.2, float(preset.get("bullet_max_lifetime", 2.8))),
        )

        return Enemy(
            x=x_pos,
            y=y_pos,
            enemy_type=enemy_type,
            hp=max(1, int(preset.get("hp", 20))),
            radius=max(6.0, float(preset.get("radius", 12.0))),
            move_speed=max(10.0, float(preset.get("move_speed", 60.0))),
            ai_mode=str(preset.get("ai_mode", "chase")),
            preferred_distance=max(80.0, float(preset.get("preferred_distance", 260.0))),
            dash_trigger_distance=max(40.0, float(preset.get("dash_trigger_distance", 130.0))),
            dash_speed_multiplier=max(1.0, float(preset.get("dash_speed_multiplier", 1.7))),
            avoid_player_bullets=bool(preset.get("avoid_player_bullets", False)),
            burst_waves=max(0, int(preset.get("burst_waves", 3))),
            burst_interval=max(0.02, float(preset.get("burst_interval", 0.2))),
            burst_cooldown=max(0.1, float(preset.get("burst_cooldown", 1.8))),
            burst_fan_count=max(1, int(preset.get("burst_fan_count", 3))),
            burst_spread=max(0.0, float(preset.get("burst_spread", 0.2))),
            burst_bullet_speed=max(30.0, float(preset.get("burst_bullet_speed", 150.0))),
            death_bloom_rings=max(0, int(preset.get("death_bloom_rings", 0))),
            visual_shape=str(preset.get("visual_shape", "circle")),
            visual_color=self._parse_color(preset.get("visual_color", [230, 80, 90]), (230, 80, 90)),
            drop_tier=max(1, int(preset.get("drop_tier", 1))),
            danmaku=danmaku,
            attack_state_timer=0.0,
            attack_waves_left=0,
        )

    @staticmethod
    def _parse_color(raw: Any, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
        """Parse RGB color from list-like data."""
        if not isinstance(raw, list) or len(raw) != 3:
            return fallback
        try:
            red = int(raw[0])
            green = int(raw[1])
            blue = int(raw[2])
        except (TypeError, ValueError):
            return fallback

        return (
            max(0, min(255, red)),
            max(0, min(255, green)),
            max(0, min(255, blue)),
        )

    def _parse_enemy_presets(self, raw: Any) -> dict[str, dict[str, Any]]:
        """Parse enemy preset table with safe fallback defaults."""
        if not isinstance(raw, dict):
            raw = {}

        parsed: dict[str, dict[str, Any]] = {}
        for key, value in raw.items():
            if isinstance(key, str) and isinstance(value, dict):
                parsed[key] = dict(value)

        if "zako_fairy_small" not in parsed:
            logger.warning("waves.json missing 'zako_fairy_small' preset; injecting default.")
            parsed["zako_fairy_small"] = {
                "hp": 18,
                "radius": 12.0,
                "move_speed": 68.0,
                "ai_mode": "chase",
                "burst_waves": 3,
                "burst_interval": 0.2,
                "burst_cooldown": 1.9,
                "burst_fan_count": 3,
                "burst_spread": 0.16,
                "burst_bullet_speed": 170.0,
                "bullet_max_lifetime": 2.8,
                "death_bloom_rings": 0,
                "visual_shape": "circle",
                "visual_color": [230, 70, 85],
            }

        return parsed

    def _parse_enemy_pools(self, raw: Any) -> list[_WaveEnemyPool]:
        """Parse weighted wave enemy pools from JSON."""
        if not isinstance(raw, list):
            raw = []

        pools: list[_WaveEnemyPool] = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            entries_raw = item.get("entries", [])
            if not isinstance(entries_raw, list):
                continue

            entries: list[_WeightedEnemyEntry] = []
            for entry in entries_raw:
                if not isinstance(entry, dict):
                    continue
                enemy_type = str(entry.get("enemy_type", "")).strip()
                if not enemy_type:
                    continue
                weight = float(entry.get("weight", 1.0))
                entries.append(_WeightedEnemyEntry(enemy_type=enemy_type, weight=max(0.0, weight)))

            if not entries:
                continue

            min_wave = max(1, int(item.get("min_wave", 1)))
            max_wave = int(item.get("max_wave", 10**9))
            if max_wave < min_wave:
                max_wave = min_wave

            pools.append(_WaveEnemyPool(min_wave=min_wave, max_wave=max_wave, entries=entries))

        if not pools:
            logger.warning("waves.json missing enemy_pools; using fallback pool.")
            pools = [
                _WaveEnemyPool(
                    min_wave=1,
                    max_wave=10**9,
                    entries=[_WeightedEnemyEntry(enemy_type="zako_fairy_small", weight=1.0)],
                )
            ]

        return pools
