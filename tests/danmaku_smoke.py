"""Minimal smoke test for the vectorized danmaku core."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from logic.danmaku_system import (
    DanmakuGroup,
    DiscreteShape,
    EmissionOperator,
    LinearMotion,
    SwirlMotion,
)


def run_smoke_test() -> None:
    """Run a short simulation and assert basic system invariants."""
    group = DanmakuGroup(
        shape=DiscreteShape(count=12, spread=1.2),
        emission=EmissionOperator(fire_rate=20.0, speed=90.0, spin_speed=1.5),
        motions=[SwirlMotion(angular_speed=0.8), LinearMotion()],
        max_bullets=4096,
        bounds=(-300.0, 300.0, -300.0, 300.0),
        max_lifetime=0.9,
    )

    time_value = 0.0
    for _ in range(120):
        time_value += 1.0 / 60.0
        group.update(t=time_value, ex=0.0, ey=0.0, px=0.0, py=0.0)

    active_count = group.pool.active_count
    assert 0 <= active_count <= group.pool.max_size
    if active_count > 0:
        assert bool(np.all(group.pool.life[:active_count] <= np.float32(group.max_lifetime + 1.0e-4)))
    print(f"smoke_test_ok active_count={active_count}")


if __name__ == "__main__":
    run_smoke_test()

