"""Smoke test for wave spawning and progression behavior."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from logic.level_system import WaveManager


def run_smoke_test() -> None:
    """Verify wave loading, spawning, and progression basics."""
    manager = WaveManager(
        data_path="assets/data/waves.json",
        random_seed=7,
    )

    assert manager.wave_count >= 1

    total_spawned = 0
    simulated_time = 0.0
    previous_wave_index = manager.current_wave_index
    advanced_once = False

    for _ in range(2000):
        simulated_time += 1.0 / 60.0
        spawned = manager.update(1.0 / 60.0, player_x=0.0, player_y=0.0)
        total_spawned += len(spawned)

        if manager.current_wave_index != previous_wave_index:
            advanced_once = True
            break

    assert total_spawned > 0
    assert advanced_once, "Expected at least one wave transition in simulation window."

    print(f"wave_manager_smoke_ok spawned={total_spawned} wave={manager.current_wave_index}")


if __name__ == "__main__":
    run_smoke_test()


