"""Camera primitives for converting world coordinates to screen space."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Camera:
    """Simple 2D camera storing world-space origin offset."""

    x: float = 0.0
    y: float = 0.0

    def apply(self, target_x: float, target_y: float) -> tuple[float, float]:
        """Convert world coordinates to screen-relative coordinates."""
        return target_x - self.x, target_y - self.y


Camera2D = Camera

