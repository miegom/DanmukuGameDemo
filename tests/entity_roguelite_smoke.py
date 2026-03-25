"""Smoke test for entity integration and roguelite upgrades."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from logic.entity import Enemy, Player
from logic.danmaku_system import HomingMotion
from logic.roguelite_system import UpgradeManager


def run_smoke_test() -> None:
    """Exercise movement, upgrade application, and danmaku updates."""
    player = Player(x=0.0, y=0.0)
    enemy = Enemy(x=0.0, y=-100.0)
    manager = UpgradeManager(data_path="assets/data/upgrades.json", random_seed=7)

    choices = manager.get_random_choices_for_player(player=player, count=3)
    assert len(choices) > 0, "Expected at least one available upgrade choice."

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

    # Regression: homing radius unlock must attach HomingMotion and steer bullets.
    homing_upgrade = {
        "id": "test_reimu_homing_ii",
        "character": "reimu",
        "type": "player_tuning",
        "param": "reimu_basic_homing_radius",
        "mode": "set",
        "value": 360,
    }
    assert manager.apply_upgrade(homing_upgrade, player), "Expected homing radius upgrade to apply."

    from scenes.gameplay_scene import GameplayScene

    scene = GameplayScene(context={"screen_width": 640, "screen_height": 360, "selected_character_id": "reimu"})
    scene.player = player
    scene._sync_basic_attack_tuning()
    homing_motions = [m for m in player.basic_weapon.motions if isinstance(m, HomingMotion)]
    assert homing_motions, "Expected homing motion to be attached after radius unlock."

    motion = homing_motions[0]
    player.is_firing = True
    player.target_angle = 0.0
    player.update_attack(t=time_value + 0.1, dt=1.0 / 60.0)
    assert player.basic_weapon.pool.active_count > 0, "Expected at least one player bullet."

    player.basic_weapon.pool.x[0] = 0.0
    player.basic_weapon.pool.y[0] = 0.0
    player.basic_weapon.pool.vx[0] = 0.0
    player.basic_weapon.pool.vy[0] = 0.0
    motion.set_enemy_points(
        enemy_x=np.asarray([100.0], dtype=np.float32),
        enemy_y=np.asarray([0.0], dtype=np.float32),
    )
    motion.apply(player.basic_weapon.pool, dt=1.0 / 60.0)
    assert float(player.basic_weapon.pool.vx[0]) > 0.0, "Expected homing to steer bullet toward +x target."

    reimu_spell_upgrade = {
        "id": "test_reimu_spell_size_i",
        "character": "reimu",
        "type": "player_tuning",
        "param": "reimu_spell_size_mul",
        "mode": "mul",
        "value": 1.2,
    }
    assert manager.apply_upgrade(reimu_spell_upgrade, player), "Expected Reimu spell tuning upgrade to apply."
    assert player.tuning.reimu_spell_size_mul > 1.0

    morisa = Player(x=0.0, y=0.0)
    morisa.character_id = "morisa"
    morisa_spell_upgrade = {
        "id": "test_morisa_spell_rate_i",
        "character": "morisa",
        "type": "player_tuning",
        "param": "morisa_spell_fire_rate_mul",
        "mode": "mul",
        "value": 1.2,
    }
    assert manager.apply_upgrade(morisa_spell_upgrade, morisa), "Expected Morisa spell tuning upgrade to apply."
    assert morisa.tuning.morisa_spell_fire_rate_mul > 1.0

    speed_upgrade = {
        "id": "test_common_move_speed",
        "character": "any",
        "type": "player_stat",
        "param": "move_speed",
        "mode": "mul",
        "value": 1.08,
    }
    hp_upgrade = {
        "id": "test_common_life",
        "character": "any",
        "type": "player_stat",
        "param": "life",
        "mode": "add",
        "value": 1,
    }
    spell_upgrade = {
        "id": "test_common_spell_capacity",
        "character": "any",
        "type": "player_stat",
        "param": "spell_capacity",
        "mode": "add",
        "value": 1,
    }

    before_speed = player.speed
    before_max_hp = player.max_hp
    before_spell_cap = player.innate_spell_stock_max

    assert manager.apply_upgrade(speed_upgrade, player), "Expected common speed upgrade to apply."
    assert manager.apply_upgrade(hp_upgrade, player), "Expected common life upgrade to apply."
    assert manager.apply_upgrade(spell_upgrade, player), "Expected common spell upgrade to apply."
    assert player.speed > before_speed
    assert player.max_hp == before_max_hp + 1
    assert player.innate_spell_stock_max == before_spell_cap + 1

    print(
        "entity_roguelite_smoke_ok "
        f"player_basic={player.basic_weapon.pool.active_count} "
        f"player_spell={player.spell_card.pool.active_count} "
        f"enemy={enemy.danmaku.pool.active_count}"
    )


if __name__ == "__main__":
    run_smoke_test()
