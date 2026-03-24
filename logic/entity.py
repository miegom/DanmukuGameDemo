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
    RingShape,
)

Boundaries = Tuple[float, float, float, float]


@dataclass(slots=True)
class Enemy:
    """Enemy actor with local state and its own danmaku group."""

    x: float
    y: float
    hp: int = 20
    radius: float = 12.0
    danmaku: DanmakuGroup = field(default_factory=lambda: DanmakuGroup(
        shape=RingShape(count=8),
        emission=EmissionOperator(fire_rate=2.0, speed=70.0, spin_speed=0.3),
        motions=[LinearMotion()],
        max_bullets=2048,
        bounds=(-320.0, 320.0, -240.0, 240.0),
    ))

    def update_attack(self, t: float, px: float, py: float) -> None:
        """Advance enemy bullet simulation for the current frame."""
        self.danmaku.update(t=t, ex=self.x, ey=self.y, px=px, py=py)


@dataclass(slots=True)
class Player:
    """Player actor with movement and two independent danmaku channels."""

    x: float = 0.0
    y: float = 0.0
    speed: float = 180.0
    radius: float = 8.0
    max_hp: int = 5
    current_hp: int = 5
    exp: int = 0
    level: int = 1
    level_up: bool = False
    basic_weapon: DanmakuGroup = field(default_factory=lambda: DanmakuGroup(
        shape=DiscreteShape(count=3, spread=0.35, base_angle=-np.pi / 2.0),
        emission=EmissionOperator(fire_rate=8.0, speed=220.0, spin_speed=0.0),
        motions=[LinearMotion()],
        max_bullets=4096,
        bounds=(-320.0, 320.0, -240.0, 240.0),
    ))
    spell_card: DanmakuGroup = field(default_factory=lambda: DanmakuGroup(
        shape=RingShape(count=14),
        emission=EmissionOperator(fire_rate=1.5, speed=130.0, spin_speed=1.2),
        motions=[LinearMotion()],
        max_bullets=4096,
        bounds=(-320.0, 320.0, -240.0, 240.0),
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
            self.x += float(direction[0]) * self.speed * dt
            self.y += float(direction[1]) * self.speed * dt

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

    def update_attack(self, t: float) -> None:
        """Advance both player danmaku channels for the current frame."""
        self.basic_weapon.update(t=t, ex=self.x, ey=self.y, px=self.x, py=self.y)
        self.spell_card.update(t=t, ex=self.x, ey=self.y, px=self.x, py=self.y)

    def get_weapon_group(self, weapon_key: str) -> DanmakuGroup:
        """Resolve weapon key to danmaku group.

        Args:
            weapon_key: ``"basic_weapon"`` or ``"spell_card"``.

        Returns:
            Matching :class:`DanmakuGroup` instance.

        Raises:
            ValueError: If the key is unknown.
        """
        if weapon_key == "basic_weapon":
            return self.basic_weapon
        if weapon_key == "spell_card":
            return self.spell_card
        raise ValueError(f"Unknown weapon key: {weapon_key}")

    def append_motion(self, weapon_key: str, motion: MotionOperator) -> None:
        """Attach a new motion operator to the selected weapon group."""
        group = self.get_weapon_group(weapon_key)
        group.motions.append(motion)


@dataclass(slots=True)
class ExpOrb:
    """Lightweight experience pickup dropped by defeated enemies."""

    x: float
    y: float
    value: int


