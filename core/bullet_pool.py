"""Vectorized bullet pool backed by preallocated NumPy arrays."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PoolView:
    """Read-only view for currently active bullet data."""

    x: np.ndarray
    y: np.ndarray
    vx: np.ndarray
    vy: np.ndarray
    life: np.ndarray


class NumpyBulletPool:
    """Store bullet state in contiguous float32 arrays for vectorized updates.

    The pool keeps active bullets compacted in ``[0, active_count)`` across all
    arrays, so downstream operators can update only one contiguous slice.
    """

    def __init__(self, max_size: int) -> None:
        """Initialize the pool with preallocated arrays.

        Args:
            max_size: Maximum number of bullets stored simultaneously.

        Raises:
            ValueError: If ``max_size`` is not positive.
        """
        if max_size <= 0:
            raise ValueError("max_size must be a positive integer.")

        self.max_size: int = max_size
        self.active_count: int = 0

        self.x: np.ndarray = np.empty(max_size, dtype=np.float32)
        self.y: np.ndarray = np.empty(max_size, dtype=np.float32)
        self.vx: np.ndarray = np.empty(max_size, dtype=np.float32)
        self.vy: np.ndarray = np.empty(max_size, dtype=np.float32)
        self.life: np.ndarray = np.empty(max_size, dtype=np.float32)

    def _active_end(self) -> int:
        """Return a sanitized active index inside ``[0, max_size]``."""
        if self.active_count < 0:
            self.active_count = 0
        elif self.active_count > self.max_size:
            self.active_count = self.max_size
        return self.active_count

    @property
    def active(self) -> PoolView:
        """Return a view of active bullet arrays."""
        end = self._active_end()
        return PoolView(
            x=self.x[:end],
            y=self.y[:end],
            vx=self.vx[:end],
            vy=self.vy[:end],
            life=self.life[:end],
        )

    def spawn_batch(
        self,
        x_arr: np.ndarray,
        y_arr: np.ndarray,
        vx_arr: np.ndarray,
        vy_arr: np.ndarray,
        life_arr: np.ndarray | None = None,
    ) -> int:
        """Append a bullet batch into the pool.

        Args:
            x_arr: Spawn x coordinates.
            y_arr: Spawn y coordinates.
            vx_arr: Velocity x components.
            vy_arr: Velocity y components.

        Returns:
            Number of bullets actually inserted after capacity clamping.

        Raises:
            ValueError: If array shapes are inconsistent.
        """
        x_flat = np.ravel(x_arr)
        y_flat = np.ravel(y_arr)
        vx_flat = np.ravel(vx_arr)
        vy_flat = np.ravel(vy_arr)

        if not (x_flat.shape == y_flat.shape == vx_flat.shape == vy_flat.shape):
            raise ValueError("spawn arrays must share the same shape.")

        batch_size = int(x_flat.size)
        if batch_size == 0:
            return 0

        active = self._active_end()
        free_space = self.max_size - self.active_count
        if free_space <= 0:
            return 0

        insert_count = min(batch_size, free_space)
        start = active
        end = start + insert_count

        self.x[start:end] = x_flat[:insert_count].astype(np.float32, copy=False)
        self.y[start:end] = y_flat[:insert_count].astype(np.float32, copy=False)
        self.vx[start:end] = vx_flat[:insert_count].astype(np.float32, copy=False)
        self.vy[start:end] = vy_flat[:insert_count].astype(np.float32, copy=False)
        if life_arr is None:
            self.life[start:end] = np.float32(0.0)
        else:
            life_flat = np.ravel(life_arr)
            if life_flat.shape != x_flat.shape:
                raise ValueError("life_arr must share the same shape as spawn arrays.")
            self.life[start:end] = life_flat[:insert_count].astype(np.float32, copy=False)

        self.active_count = end
        return insert_count

    def filter_active(self, valid_mask: np.ndarray) -> int:
        """Compact arrays in-place by applying an active-bullet mask.

        Args:
            valid_mask: Boolean mask with length equal to ``active_count``.

        Returns:
            Number of surviving bullets after compaction.

        Raises:
            ValueError: If mask shape or dtype is invalid.
        """
        active = self._active_end()
        if valid_mask.dtype != np.bool_:
            raise ValueError("valid_mask must have dtype bool.")
        if valid_mask.ndim != 1 or valid_mask.shape[0] != active:
            raise ValueError("valid_mask length must equal active_count.")

        survivor_count = int(np.count_nonzero(valid_mask))
        if survivor_count > 0:
            active_slice = slice(0, active)
            self.x[:survivor_count] = self.x[active_slice][valid_mask]
            self.y[:survivor_count] = self.y[active_slice][valid_mask]
            self.vx[:survivor_count] = self.vx[active_slice][valid_mask]
            self.vy[:survivor_count] = self.vy[active_slice][valid_mask]
            self.life[:survivor_count] = self.life[active_slice][valid_mask]

        self.active_count = survivor_count
        return survivor_count

