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
class OrbitMotion(MotionOperator):
    """Bullets orbit around the emitter (player)."""

    angular_speed: float
    center_x: float = 0.0
    center_y: float = 0.0

    def apply(self, pool: NumpyBulletPool, dt: float) -> None:
        """Apply vectorized rotation around a center point."""
        if pool.active_count == 0 or dt <= 0.0 or self.angular_speed == 0.0:
            return

        active = pool.active_count
        theta = np.float32(self.angular_speed * dt)
        cos_theta = np.float32(np.cos(theta))
        sin_theta = np.float32(np.sin(theta))

        # Relative positions
        rx = pool.x[:active] - np.float32(self.center_x)
        ry = pool.y[:active] - np.float32(self.center_y)

        # Rotate positions
        pool.x[:active] = np.float32(self.center_x) + (rx * cos_theta - ry * sin_theta)
        pool.y[:active] = np.float32(self.center_y) + (rx * sin_theta + ry * cos_theta)

        # Rotate velocities to keep them tangent or pointing out
        vx = pool.vx[:active].copy()
        vy = pool.vy[:active].copy()
        pool.vx[:active] = (vx * cos_theta) - (vy * sin_theta)
        pool.vy[:active] = (vx * sin_theta) + (vy * cos_theta)


@dataclass(slots=True)
class HomingMotion(MotionOperator):
    """Bullets accelerate with radius-based target lock for one danmaku group."""

    acceleration: float
    max_distance: float = 0.0
    lock_duration: float = 0.35
    target_x: float = 0.0
    target_y: float = 0.0

    _enemy_x: np.ndarray = field(init=False, default_factory=lambda: np.empty(0, dtype=np.float32), repr=False)
    _enemy_y: np.ndarray = field(init=False, default_factory=lambda: np.empty(0, dtype=np.float32), repr=False)
    _lock_timer: float = field(init=False, default=0.0, repr=False)
    _turn_boost: float = field(init=False, default=2.2, repr=False)

    def set_enemy_points(self, enemy_x: np.ndarray, enemy_y: np.ndarray) -> None:
        """Set enemy positions snapshot for this frame."""
        if enemy_x.ndim != 1 or enemy_y.ndim != 1 or enemy_x.size != enemy_y.size:
            self._enemy_x = np.empty(0, dtype=np.float32)
            self._enemy_y = np.empty(0, dtype=np.float32)
            return

        self._enemy_x = enemy_x.astype(np.float32, copy=False)
        self._enemy_y = enemy_y.astype(np.float32, copy=False)

    def set_homing_params(self, *, radius: float, acceleration: float, lock_duration: float) -> None:
        """Update runtime homing parameters."""
        self.max_distance = max(0.0, float(radius))
        self.acceleration = max(0.0, float(acceleration))
        self.lock_duration = max(0.0, float(lock_duration))

    def apply(self, pool: NumpyBulletPool, dt: float) -> None:
        """Apply acceleration towards a locked target acquired within detection radius."""
        if pool.active_count == 0 or dt <= 0.0 or self.acceleration <= 0.0:
            return

        self._lock_timer = max(0.0, self._lock_timer - dt)

        if self._lock_timer <= 0.0:
            self._try_acquire_target(pool)
        elif self._enemy_x.size > 0:
            self._refresh_target_from_snapshot()

        if self._lock_timer <= 0.0:
            return

        active = pool.active_count
        old_vx = pool.vx[:active].copy()
        old_vy = pool.vy[:active].copy()
        old_speed = np.sqrt(old_vx * old_vx + old_vy * old_vy)

        dx = np.float32(self.target_x) - pool.x[:active]
        dy = np.float32(self.target_y) - pool.y[:active]
        dist = np.maximum(np.sqrt(dx * dx + dy * dy), np.float32(1.0e-6))
        accel_scale = np.float32(self.acceleration * self._turn_boost * dt)
        pool.vx[:active] += (dx / dist) * accel_scale
        pool.vy[:active] += (dy / dist) * accel_scale

        # Keep speed magnitude stable while allowing faster heading change.
        new_speed = np.sqrt(pool.vx[:active] * pool.vx[:active] + pool.vy[:active] * pool.vy[:active])
        safe_new = np.maximum(new_speed, np.float32(1.0e-6))
        keep_speed = old_speed > np.float32(1.0e-6)
        pool.vx[:active] = np.where(keep_speed, (pool.vx[:active] / safe_new) * old_speed, pool.vx[:active])
        pool.vy[:active] = np.where(keep_speed, (pool.vy[:active] / safe_new) * old_speed, pool.vy[:active])

    def _try_acquire_target(self, pool: NumpyBulletPool) -> None:
        """Acquire a target when any active bullet has an enemy inside radius."""
        if self.max_distance <= 0.0 or self.lock_duration <= 0.0:
            return
        if self._enemy_x.size == 0 or pool.active_count <= 0:
            return

        active = pool.active_count
        bullet_x = pool.x[:active]
        bullet_y = pool.y[:active]

        dx = self._enemy_x[np.newaxis, :] - bullet_x[:, np.newaxis]
        dy = self._enemy_y[np.newaxis, :] - bullet_y[:, np.newaxis]
        dist_sq = (dx * dx) + (dy * dy)
        in_range = dist_sq <= np.float32(self.max_distance * self.max_distance)
        if not np.any(in_range):
            return

        masked = np.where(in_range, dist_sq, np.float32(np.inf))
        nearest_flat = int(np.argmin(masked))
        enemy_index = nearest_flat % self._enemy_x.size

        self.target_x = float(self._enemy_x[enemy_index])
        self.target_y = float(self._enemy_y[enemy_index])
        self._lock_timer = self.lock_duration

    def _refresh_target_from_snapshot(self) -> None:
        """Keep target pointing at the nearest enemy to previous lock point."""
        if self._enemy_x.size == 0:
            return

        dx = self._enemy_x - np.float32(self.target_x)
        dy = self._enemy_y - np.float32(self.target_y)
        index = int(np.argmin((dx * dx) + (dy * dy)))
        self.target_x = float(self._enemy_x[index])
        self.target_y = float(self._enemy_y[index])


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
    max_lifetime: float = 3.2

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

        active = self.__pool.active_count
        if active > 0 and dt > 0.0:
            self.__pool.life[:active] += np.float32(dt)

        for operator in self.motions:
            operator.apply(self.__pool, dt)

        self._cull_out_of_bounds()

    def emit_burst(self, shots: int, t: float, ex: float, ey: float, px: float, py: float) -> None:
        """Emit a fixed number of shots immediately, without changing motion update order."""
        if shots <= 0:
            return

        fire_rate = float(self.emission.fire_rate)
        if fire_rate <= 0.0:
            return

        burst_dt = np.float32(shots / fire_rate)
        self._emit_batch(t=t, dt=float(burst_dt), ex=ex, ey=ey, px=px, py=py)

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
        if self.max_lifetime > 0.0:
            valid_mask &= self.__pool.life[:active] <= np.float32(self.max_lifetime)
        self.__pool.filter_active(valid_mask)
