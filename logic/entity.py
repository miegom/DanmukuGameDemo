"""Entity layer built on top of the vectorized danmaku system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

import numpy as np

from logic.danmaku_system import (
    DanmakuGroup,
    DiscreteShape,
    EmissionOperator,
    LinearMotion,
    MotionOperator,
    OrbitMotion,
    RingShape,
)

Boundaries = Tuple[float, float, float, float]


@dataclass(slots=True)
class PlayerTuning:
    """Runtime-tunable basic and spell-card parameters driven by upgrades."""

    reimu_basic_interval_mul: float = 1.0
    reimu_basic_speed_mul: float = 1.0
    reimu_basic_extra_count: int = 0
    reimu_basic_size_mul: float = 1.0
    reimu_basic_homing_radius: float = 0.0
    reimu_basic_homing_accel: float = 0.0
    reimu_basic_homing_duration: float = 0.0
    reimu_spell_extra_orbs: int = 0
    reimu_spell_size_mul: float = 1.0
    reimu_spell_life_mul: float = 1.0

    morisa_basic_interval_mul: float = 1.0
    morisa_basic_width_mul: float = 1.0
    morisa_basic_extra_lasers: int = 0
    morisa_spell_fire_rate_mul: float = 1.0
    morisa_spell_extra_width_mul: float = 1.0
    morisa_spell_extra_lasers: int = 0


@dataclass(slots=True)
class Enemy:
    """Enemy actor with local state and its own danmaku group."""

    x: float
    y: float
    enemy_type: str = "zako_fairy_small"
    hp: int = 20
    radius: float = 12.0
    move_speed: float = 60.0
    ai_mode: str = "chase"
    preferred_distance: float = 260.0
    dash_trigger_distance: float = 130.0
    dash_speed_multiplier: float = 1.7
    avoid_player_bullets: bool = False
    burst_waves: int = 3
    burst_interval: float = 0.2
    burst_cooldown: float = 1.8
    burst_fan_count: int = 3
    burst_spread: float = 0.2
    burst_bullet_speed: float = 150.0
    death_bloom_rings: int = 0
    visual_shape: str = "circle"
    visual_color: tuple[int, int, int] = (230, 80, 90)
    drop_tier: int = 1

    attack_state_timer: float = 0.0
    attack_waves_left: int = 0

    danmaku: DanmakuGroup = field(default_factory=lambda: DanmakuGroup(
        shape=RingShape(count=8),
        emission=EmissionOperator(fire_rate=2.0, speed=70.0, spin_speed=0.3),
        motions=[LinearMotion()],
        max_bullets=2048,
        bounds=(-320.0, 320.0, -240.0, 240.0),
        max_lifetime=2.6,
    ))

    def update_attack(self, t: float, px: float, py: float) -> None:
        """Advance enemy bullet simulation for the current frame."""
        self.danmaku.update(t=t, ex=self.x, ey=self.y, px=px, py=py)


@dataclass(slots=True)
class Player:
    """Player actor with movement and two independent danmaku channels."""

    x: float = 0.0
    y: float = 0.0
    character_id: str = "reimu"
    speed: float = 200.0
    focus_speed_multiplier: float = 0.45
    radius: float = 8.0
    hitbox_radius: float = 3.0
    max_hp: int = 5
    current_hp: int = 5
    exp: int = 0
    level: int = 1
    level_up: bool = False
    is_focus_mode: bool = False
    is_firing: bool = False
    target_angle: float = -np.pi / 2.0
    spell_cooldown: float = 0.0
    spell_cooldown_max: float = 3.0
    innate_spell_stock: int = 1
    innate_spell_stock_max: int = 1
    innate_spell_recover_time: float = 12.0
    innate_spell_recover_timer: float = 0.0
    drop_spell_stock: int = 0
    _pending_spell_shots: int = 0
    applied_upgrade_ids: set[str] = field(default_factory=set)
    tuning: PlayerTuning = field(default_factory=PlayerTuning)

    basic_weapon: DanmakuGroup = field(default_factory=lambda: DanmakuGroup(
        shape=DiscreteShape(count=3, spread=0.35, base_angle=-np.pi / 2.0),
        emission=EmissionOperator(fire_rate=8.0, speed=220.0, spin_speed=0.0),
        motions=[LinearMotion()],
        max_bullets=4096,
        bounds=(-320.0, 320.0, -240.0, 240.0),
        max_lifetime=2.4,
    ))
    spell_card: DanmakuGroup = field(default_factory=lambda: DanmakuGroup(
        shape=RingShape(count=14),
        emission=EmissionOperator(fire_rate=1.5, speed=130.0, spin_speed=1.2),
        motions=[LinearMotion()],
        max_bullets=4096,
        bounds=(-320.0, 320.0, -240.0, 240.0),
        max_lifetime=3.0,
    ))

    def update_movement(
        self,
        dx: float,
        dy: float,
        dt: float,
        boundaries: Boundaries,
    ) -> None:
        """Move player with normalized input and world-bound clamping.

        Args:
            dx: Horizontal input in range ``[-1, 1]``.
            dy: Vertical input in range ``[-1, 1]``.
            dt: Frame delta time in seconds.
            boundaries: Playfield bounds as ``(x_min, x_max, y_min, y_max)``.
        """
        if dt <= 0.0:
            return

        direction = np.asarray([dx, dy], dtype=np.float32)
        length = float(np.linalg.norm(direction))
        if length > 1.0e-6:
            direction /= np.float32(length)
            current_speed = self.speed
            if self.is_focus_mode:
                current_speed *= self.focus_speed_multiplier
            self.x += float(direction[0]) * current_speed * dt
            self.y += float(direction[1]) * current_speed * dt

        x_min, x_max, y_min, y_max = boundaries
        self.x = max(x_min, min(x_max, self.x))
        self.y = max(y_min, min(y_max, self.y))

    def gain_exp(self, amount: int) -> bool:
        """Add experience and set level-up flag when threshold is reached.

        Args:
            amount: Experience points to add.

        Returns:
            ``True`` if at least one level-up is triggered.
        """
        if amount <= 0:
            return False

        self.exp += amount
        leveled_up = False

        while self.exp >= self.level * 100:
            self.exp -= self.level * 100
            self.level += 1
            self.max_hp += 1
            self.current_hp = min(self.current_hp + 1, self.max_hp)
            leveled_up = True

        self.level_up = leveled_up
        return leveled_up

    def update_attack(self, t: float, dt: float = 1.0 / 60.0) -> None:
        """Advance player weapons for the current frame."""
        if dt > 0.0:
            self.update_spell_recharge(dt)

        if hasattr(self.basic_weapon.shape, "base_angle"):
            self.basic_weapon.shape.base_angle = self.target_angle

        for motion in self.spell_card.motions:
            if isinstance(motion, OrbitMotion):
                motion.center_x = self.x
                motion.center_y = self.y

        self._update_group_with_optional_emission(self.basic_weapon, t=t, can_emit=self.is_firing)

        if self._pending_spell_shots > 0:
            self.spell_card.emit_burst(
                shots=self._pending_spell_shots,
                t=t,
                ex=self.x,
                ey=self.y,
                px=self.x,
                py=self.y,
            )
            self._pending_spell_shots = 0

        self._update_group_with_optional_emission(self.spell_card, t=t, can_emit=False)

    def trigger_spell(self, t: float) -> None:
        """Queue a 3-ring spell burst when cooldown is ready."""
        del t
        if self.consume_one_spell_charge() <= 0:
            return

        self._pending_spell_shots = 3

    def consume_one_spell_charge(self) -> int:
        """Consume one spell charge, prioritizing dropped stock, then innate stock."""
        if self.drop_spell_stock > 0:
            self.drop_spell_stock -= 1
            return 1

        if self.innate_spell_stock > 0:
            self.innate_spell_stock -= 1
            if self.innate_spell_stock < self.innate_spell_stock_max:
                self.innate_spell_recover_timer = max(self.innate_spell_recover_timer, self.innate_spell_recover_time)
                self.spell_cooldown = self.innate_spell_recover_timer
            return 1

        return 0

    def available_spell_charges(self) -> int:
        """Return total available spell casts from innate and dropped stocks."""
        return max(0, self.innate_spell_stock) + max(0, self.drop_spell_stock)

    def add_drop_spell_stock(self, amount: int = 1) -> None:
        """Increase stackable dropped spell stock."""
        if amount <= 0:
            return
        self.drop_spell_stock += int(amount)

    def increase_innate_spell_capacity(self, amount: int = 1) -> bool:
        """Increase innate spell capacity and fill the newly added slots."""
        if amount <= 0:
            return False

        self.innate_spell_stock_max += int(amount)
        self.innate_spell_stock = min(self.innate_spell_stock + int(amount), self.innate_spell_stock_max)
        self.innate_spell_recover_timer = 0.0
        self.spell_cooldown = 0.0
        return True

    def update_spell_recharge(self, dt: float) -> None:
        """Recharge innate one-slot spell stock over time."""
        if dt <= 0.0:
            return

        if self.innate_spell_stock >= self.innate_spell_stock_max:
            self.innate_spell_recover_timer = 0.0
            self.spell_cooldown = 0.0
            return

        self.innate_spell_recover_timer = max(0.0, self.innate_spell_recover_timer - dt)
        self.spell_cooldown = self.innate_spell_recover_timer
        if self.innate_spell_recover_timer <= 0.0:
            self.innate_spell_stock = self.innate_spell_stock_max
            self.spell_cooldown = 0.0

    def consume_all_spell_charges(self) -> int:
        """Consume all available spell charges and start innate recovery when needed."""
        innate_used = min(self.innate_spell_stock, self.innate_spell_stock_max)
        dropped_used = max(0, self.drop_spell_stock)
        total = innate_used + dropped_used
        if total <= 0:
            return 0

        self.innate_spell_stock -= innate_used
        self.drop_spell_stock = 0

        if innate_used > 0 and self.innate_spell_stock < self.innate_spell_stock_max:
            self.innate_spell_recover_timer = max(self.innate_spell_recover_timer, self.innate_spell_recover_time)
            self.spell_cooldown = self.innate_spell_recover_timer

        return total

    def get_weapon_group(self, weapon_key: str) -> DanmakuGroup:
        """Resolve weapon key to danmaku group."""
        if weapon_key == "basic_weapon":
            return self.basic_weapon
        if weapon_key == "spell_card":
            return self.spell_card
        raise ValueError(f"Unknown weapon key: {weapon_key}")

    def append_motion(self, weapon_key: str, motion: MotionOperator) -> None:
        """Attach a new motion operator to the selected weapon group."""
        group = self.get_weapon_group(weapon_key)
        group.motions.append(motion)

    def apply_tuning(self, param: str, mode: str, value: float) -> bool:
        """Apply one numeric mutation to :class:`PlayerTuning`."""
        if not hasattr(self.tuning, param):
            return False

        current = getattr(self.tuning, param)
        if mode == "add":
            updated = current + value
        elif mode == "mul":
            updated = current * value
        elif mode == "set":
            updated = value
        else:
            return False

        if isinstance(current, int):
            setattr(self.tuning, param, int(round(updated)))
            return True

        setattr(self.tuning, param, float(updated))
        return True

    def _update_group_with_optional_emission(self, group: DanmakuGroup, t: float, can_emit: bool) -> None:
        """Advance bullets while optionally disabling this frame's emission."""
        if can_emit:
            group.update(t=t, ex=self.x, ey=self.y, px=self.x, py=self.y)
            return

        original_rate = group.emission.fire_rate
        group.emission.fire_rate = 0.0
        try:
            group.update(t=t, ex=self.x, ey=self.y, px=self.x, py=self.y)
        finally:
            group.emission.fire_rate = original_rate


@dataclass(slots=True)
class ExpOrb:
    """Lightweight experience pickup dropped by defeated enemies."""

    x: float
    y: float
    value: int
    kind: str = "exp"

