"""Vectorized Danmaku system based on data-oriented design."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from core.bullet_pool import NumpyBulletPool


class BaseShape(ABC):
    """Base shape contract for angle sampling in radians."""

    @abstractmethod
    def angles(self, t: float) -> np.ndarray:
        """Return firing angles in radians as a float32 NumPy array."""


@dataclass(slots=True)
class RingShape(BaseShape):
    """Emit bullets with uniformly distributed full-circle angles."""

    count: int
    base_angle: float = 0.0

    def angles(self, t: float) -> np.ndarray:
        """Return evenly spaced angles on ``[0, 2pi)``.

        The parameter ``t`` is accepted for polymorphic compatibility.
        """
        del t
        if self.count <= 0:
            return np.empty(0, dtype=np.float32)

        values = np.linspace(
            0.0,
            2.0 * np.pi,
            num=self.count,
            endpoint=False,
            dtype=np.float32,
        )
        return values + np.float32(self.base_angle)


@dataclass(slots=True)
class DiscreteShape(BaseShape):
    """Emit bullets in a discrete fan spread around ``base_angle``."""

    count: int
    spread: float
    base_angle: float = 0.0

    def angles(self, t: float) -> np.ndarray:
        """Return fan angles distributed on ``[-spread/2, spread/2]``."""
        del t
        if self.count <= 0:
            return np.empty(0, dtype=np.float32)
        if self.count == 1:
            return np.asarray([self.base_angle], dtype=np.float32)

        offsets = np.linspace(
            -0.5 * self.spread,
            0.5 * self.spread,
            num=self.count,
            endpoint=True,
            dtype=np.float32,
        )
        return offsets + np.float32(self.base_angle)


@dataclass(slots=True)
class EmissionOperator:
    """Emission parameters controlling rate, speed, and rotation over time."""

    fire_rate: float
    speed: float
    spin_speed: float = 0.0


class MotionOperator(ABC):
    """Base interface for vectorized bullet motion transforms."""

    @abstractmethod
    def apply(self, pool: NumpyBulletPool, dt: float) -> None:
        """Apply this operator to all active bullets in ``pool``."""


@dataclass(slots=True)
class LinearMotion(MotionOperator):
    """Linear integrator where position follows velocity."""

    def apply(self, pool: NumpyBulletPool, dt: float) -> None:
        """Apply vectorized position integration to active bullets."""
        if pool.active_count == 0 or dt <= 0.0:
            return

        active = pool.active_count
        pool.x[:active] += pool.vx[:active] * np.float32(dt)
        pool.y[:active] += pool.vy[:active] * np.float32(dt)


@dataclass(slots=True)
class SwirlMotion(MotionOperator):
    """Rotate velocity vectors by a constant angular speed each frame."""

    angular_speed: float

    def apply(self, pool: NumpyBulletPool, dt: float) -> None:
        """Apply a vectorized 2D rotation matrix to active velocities."""
        if pool.active_count == 0 or dt <= 0.0 or self.angular_speed == 0.0:
            return

        active = pool.active_count
        theta = np.float32(self.angular_speed * dt)
        cos_theta = np.float32(np.cos(theta))
        sin_theta = np.float32(np.sin(theta))

        vx = pool.vx[:active].copy()
        vy = pool.vy[:active].copy()

        pool.vx[:active] = (vx * cos_theta) - (vy * sin_theta)
        pool.vy[:active] = (vx * sin_theta) + (vy * cos_theta)


@dataclass(slots=True)
class DanmakuGroup:
    """Composable danmaku group with vectorized emission and movement."""

    shape: BaseShape
    emission: EmissionOperator
    motions: list[MotionOperator] = field(default_factory=list)
    max_bullets: int = 8192
    bounds: tuple[float, float, float, float] = (-256.0, 256.0, -256.0, 256.0)

    __pool: NumpyBulletPool = field(init=False, repr=False)
    __last_t: float | None = field(init=False, default=None, repr=False)
    __emit_credit: float = field(init=False, default=0.0, repr=False)

    def __post_init__(self) -> None:
        """Initialize private bullet storage."""
        self.__pool = NumpyBulletPool(max_size=self.max_bullets)

    @property
    def pool(self) -> NumpyBulletPool:
        """Expose private pool for render/query stages."""
        return self.__pool

    def update(self, t: float, ex: float, ey: float, px: float, py: float) -> None:
        """Emit and update bullets for a frame using fully vectorized math.

        Args:
            t: Absolute timeline in seconds.
            ex: Emitter x position.
            ey: Emitter y position.
            px: Player x position in world coordinates.
            py: Player y position in world coordinates.
        """
        if self.__last_t is None:
            self.__last_t = t

        dt = max(0.0, t - self.__last_t)
        self.__last_t = t

        self._emit_batch(t=t, dt=dt, ex=ex, ey=ey, px=px, py=py)

        for operator in self.motions:
            operator.apply(self.__pool, dt)

        self._cull_out_of_bounds()

    def _emit_batch(
        self,
        t: float,
        dt: float,
        ex: float,
        ey: float,
        px: float,
        py: float,
    ) -> None:
        """Emit multiple shots in one frame without per-bullet loops."""
        del px, py
        fire_rate = self.emission.fire_rate
        if fire_rate <= 0.0:
            return

        self.__emit_credit += dt * fire_rate
        shot_count = int(self.__emit_credit)
        if shot_count <= 0:
            return
        self.__emit_credit -= shot_count

        base_angles = self.shape.angles(t)
        bullet_count = int(base_angles.size)
        if bullet_count == 0:
            return

        interval = np.float32(1.0 / fire_rate)
        shot_offsets = np.arange(shot_count, dtype=np.float32)
        shot_times = np.float32(t) - (np.float32(shot_count - 1) - shot_offsets) * interval
        spin_angles = shot_times * np.float32(self.emission.spin_speed)

        all_angles = base_angles[np.newaxis, :] + spin_angles[:, np.newaxis]
        flat_angles = all_angles.reshape(-1)

        total = flat_angles.size
        x_batch = np.full(total, np.float32(ex), dtype=np.float32)
        y_batch = np.full(total, np.float32(ey), dtype=np.float32)

        speed = np.float32(self.emission.speed)
        vx_batch = np.cos(flat_angles).astype(np.float32, copy=False) * speed
        vy_batch = np.sin(flat_angles).astype(np.float32, copy=False) * speed

        self.__pool.spawn_batch(x_batch, y_batch, vx_batch, vy_batch)

    def _cull_out_of_bounds(self) -> None:
        """Apply vectorized bounds filtering and compact active arrays."""
        active = self.__pool.active_count
        if active == 0:
            return

        x_min, x_max, y_min, y_max = self.bounds

        x_vals = self.__pool.x[:active]
        y_vals = self.__pool.y[:active]
        valid_mask = (
            (x_vals >= x_min)
            & (x_vals <= x_max)
            & (y_vals >= y_min)
            & (y_vals <= y_max)
        )
        self.__pool.filter_active(valid_mask)

