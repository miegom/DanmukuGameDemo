"""Smoke test for entity integration and roguelite upgrades."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from logic.entity import Enemy, Player
from logic.roguelite_system import UpgradeManager


def run_smoke_test() -> None:
    """Exercise movement, upgrade application, and danmaku updates."""
    player = Player(x=0.0, y=0.0)
    enemy = Enemy(x=0.0, y=-100.0)
    manager = UpgradeManager(data_path="assets/data/upgrades.json", random_seed=7)

    choices = manager.get_random_choices(count=3)
    assert len(choices) == 3, "Expected 3 upgrade choices from seeded pool."

    applied_count = 0
    for upgrade in choices:
        if manager.apply_upgrade(upgrade, player):
            applied_count += 1

    assert applied_count >= 1, "At least one upgrade should be applied successfully."

    bounds = (-200.0, 200.0, -150.0, 150.0)
    time_value = 0.0
    for _ in range(90):
        time_value += 1.0 / 60.0
        player.update_movement(dx=1.0, dy=-0.25, dt=1.0 / 60.0, boundaries=bounds)
        player.update_attack(t=time_value)
        enemy.update_attack(t=time_value, px=player.x, py=player.y)

    assert bounds[0] <= player.x <= bounds[1]
    assert bounds[2] <= player.y <= bounds[3]
    assert player.basic_weapon.pool.active_count >= 0
    assert player.spell_card.pool.active_count >= 0
    assert enemy.danmaku.pool.active_count >= 0

    print(
        "entity_roguelite_smoke_ok "
        f"player_basic={player.basic_weapon.pool.active_count} "
        f"player_spell={player.spell_card.pool.active_count} "
        f"enemy={enemy.danmaku.pool.active_count}"
    )


if __name__ == "__main__":
    run_smoke_test()

