"""Roguelite upgrade pool and runtime application logic."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from core.logger import logger
from core.resource_mgr import ResourceManager
from logic.danmaku_system import (
    EmissionOperator,
    HomingMotion,
    MotionOperator,
    OrbitMotion,
    SwirlMotion,
)
from logic.entity import Player


@dataclass(slots=True)
class UpgradeManager:
    """Load, sample, and apply roguelite upgrades."""

    data_path: str = "assets/data/upgrades.json"
    random_seed: int | None = None
    _pool: list[dict[str, Any]] = field(init=False, default_factory=list, repr=False)
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize RNG and load upgrade definitions."""
        self._rng = random.Random(self.random_seed)
        self.reload_pool()

    def reload_pool(self) -> None:
        """Reload upgrades from JSON data source."""
        payload = ResourceManager.load_json(self.data_path)
        raw_pool = payload.get("upgrades", []) if isinstance(payload, dict) else []
        self._pool = [item for item in raw_pool if isinstance(item, dict)]
        logger.info("Upgrade pool loaded: %d items", len(self._pool))

    def get_random_choices(self, count: int = 3) -> list[dict[str, Any]]:
        """Draw random unique upgrades from the full pool."""
        if count <= 0 or not self._pool:
            return []

        actual_count = min(count, len(self._pool))
        choices = self._rng.sample(self._pool, k=actual_count)
        return [dict(item) for item in choices]

    def get_random_choices_for_player(self, player: Player, count: int = 3) -> list[dict[str, Any]]:
        """Draw random upgrades filtered by character and progression state."""
        if count <= 0 or not self._pool:
            return []

        available = [
            item
            for item in self._pool
            if self._is_upgrade_available_for_player(item, player)
        ]
        if not available:
            return []

        actual_count = min(count, len(available))
        choices = self._rng.sample(available, k=actual_count)
        return [dict(item) for item in choices]

    def apply_upgrade(self, upgrade_dict: dict[str, Any], player: Player) -> bool:
        """Apply one upgrade entry to a player instance.

        Supported upgrade schemas:

        1) Emission parameter mutation:
           ``{"type": "emission", "target": "basic_weapon", "param": "fire_rate",
           "mode": "add", "value": 1.0}``

        2) Motion operator attachment:
           ``{"type": "motion", "target": "spell_card", "motion": "swirl",
           "params": {"angular_speed": 0.8}}``

        Args:
            upgrade_dict: Upgrade definition dictionary.
            player: Player receiving the upgrade.

        Returns:
            ``True`` if upgrade is applied successfully, otherwise ``False``.
        """
        target = str(upgrade_dict.get("target", "basic_weapon"))
        upgrade_type = str(upgrade_dict.get("type", "")).lower()
        upgrade_name = str(upgrade_dict.get("name", "unknown"))
        upgrade_id = str(upgrade_dict.get("id", "")).strip()

        if not self._is_upgrade_available_for_player(upgrade_dict, player):
            logger.warning("Upgrade '%s' is not available for %s", upgrade_name, player.character_id)
            return False

        if upgrade_type == "player_tuning":
            changed = self._apply_player_tuning_upgrade(upgrade_dict, player)
            if changed:
                if upgrade_id:
                    player.applied_upgrade_ids.add(upgrade_id)
                logger.info("Applied upgrade: %s", upgrade_name)
            return changed

        if upgrade_type == "player_stat":
            changed = self._apply_player_stat_upgrade(upgrade_dict, player)
            if changed:
                if upgrade_id:
                    player.applied_upgrade_ids.add(upgrade_id)
                logger.info("Applied upgrade: %s", upgrade_name)
            return changed

        try:
            weapon_group = player.get_weapon_group(target)
        except ValueError as exc:
            logger.error("Upgrade target error: %s", exc)
            return False

        if upgrade_type == "emission":
            changed = self._apply_emission_upgrade(upgrade_dict, weapon_group.emission)
            if changed:
                if upgrade_id:
                    player.applied_upgrade_ids.add(upgrade_id)
                logger.info("Applied upgrade: %s", upgrade_name)
            return changed

        if upgrade_type == "motion":
            before_count = len(weapon_group.motions)
            motion = self._build_motion(upgrade_dict)
            if motion is None:
                return False
            weapon_group.motions.append(motion)
            after_count = len(weapon_group.motions)
            logger.info(
                "Applied motion upgrade '%s' to %s",
                upgrade_name,
                target,
            )
            logger.info(
                "Motion operator count changed: %d -> %d",
                before_count,
                after_count,
            )
            logger.info("Applied upgrade: %s", upgrade_name)
            if upgrade_id:
                player.applied_upgrade_ids.add(upgrade_id)
            return True

        logger.error("Unsupported upgrade type: %s", upgrade_type)
        return False

    def _apply_emission_upgrade(
        self,
        upgrade: dict[str, Any],
        emission: EmissionOperator,
    ) -> bool:
        """Apply numeric mutation on emission parameters."""
        param = str(upgrade.get("param", ""))
        mode = str(upgrade.get("mode", "add")).lower()
        value_raw = upgrade.get("value", 0.0)

        if not hasattr(emission, param):
            logger.error("Emission has no parameter '%s'", param)
            return False

        try:
            value = float(value_raw)
            current = float(getattr(emission, param))
        except (TypeError, ValueError):
            logger.error("Invalid emission upgrade value: %s", value_raw)
            return False

        if mode == "add":
            updated = current + value
        elif mode == "mul":
            updated = current * value
        elif mode == "set":
            updated = value
        else:
            logger.error("Unsupported emission upgrade mode: %s", mode)
            return False

        setattr(emission, param, updated)
        logger.info(
            "Applied emission upgrade on '%s': %.3f -> %.3f",
            param,
            current,
            updated,
        )
        if updated == current:
            logger.warning("Emission upgrade '%s' did not change value.", param)
        return True

    def _build_motion(self, upgrade: dict[str, Any]) -> MotionOperator | None:
        """Construct a motion operator from upgrade data."""
        motion_name = str(upgrade.get("motion", "")).lower()
        params = upgrade.get("params", {})
        if not isinstance(params, dict):
            logger.error("Motion params must be a dictionary.")
            return None

        if motion_name == "swirl":
            angular_speed = float(params.get("angular_speed", 0.8))
            return SwirlMotion(angular_speed=angular_speed)

        if motion_name == "orbit":
            angular_speed = float(params.get("angular_speed", 2.5))
            return OrbitMotion(angular_speed=angular_speed)

        if motion_name == "homing":
            acceleration = float(params.get("acceleration", 150.0))
            radius = float(params.get("max_distance", 0.0))
            lock_duration = float(params.get("lock_duration", 0.35))
            return HomingMotion(
                acceleration=acceleration,
                max_distance=radius,
                lock_duration=lock_duration,
            )

        logger.error("Unsupported motion type: %s", motion_name)
        return None

    def _apply_player_tuning_upgrade(self, upgrade: dict[str, Any], player: Player) -> bool:
        """Apply numeric mutation on player tuning fields."""
        param = str(upgrade.get("param", "")).strip()
        mode = str(upgrade.get("mode", "add")).lower()
        value_raw = upgrade.get("value", 0.0)

        try:
            value = float(value_raw)
        except (TypeError, ValueError):
            logger.error("Invalid player tuning value: %s", value_raw)
            return False

        changed = player.apply_tuning(param=param, mode=mode, value=value)
        if not changed:
            logger.error("Player tuning has no parameter '%s' or mode unsupported.", param)
            return False

        logger.info("Applied player tuning upgrade on '%s' (mode=%s, value=%.3f)", param, mode, value)
        return True

    def _apply_player_stat_upgrade(self, upgrade: dict[str, Any], player: Player) -> bool:
        """Apply direct player stat upgrade for universal survival options."""
        param = str(upgrade.get("param", "")).strip().lower()
        mode = str(upgrade.get("mode", "add")).strip().lower()
        value_raw = upgrade.get("value", 0.0)

        try:
            value = float(value_raw)
        except (TypeError, ValueError):
            logger.error("Invalid player stat value: %s", value_raw)
            return False

        if param == "move_speed":
            old_speed = float(player.speed)
            if mode == "add":
                player.speed = max(10.0, old_speed + value)
            elif mode == "mul":
                player.speed = max(10.0, old_speed * value)
            elif mode == "set":
                player.speed = max(10.0, value)
            else:
                logger.error("Unsupported move_speed mode: %s", mode)
                return False
            logger.info("Applied player stat move_speed: %.2f -> %.2f", old_speed, player.speed)
            return True

        if param == "life":
            delta = int(round(value))
            if delta <= 0:
                logger.error("life upgrade value must be positive.")
                return False
            old_max_hp = int(player.max_hp)
            old_hp = int(player.current_hp)
            player.max_hp += delta
            player.current_hp = min(player.max_hp, player.current_hp + delta)
            logger.info("Applied player stat life: hp %d/%d -> %d/%d", old_hp, old_max_hp, player.current_hp, player.max_hp)
            return True

        if param == "spell_capacity":
            delta = int(round(value))
            changed = player.increase_innate_spell_capacity(delta)
            if not changed:
                logger.error("spell_capacity upgrade value must be positive.")
                return False
            logger.info(
                "Applied player stat spell_capacity: innate=%d/%d",
                player.innate_spell_stock,
                player.innate_spell_stock_max,
            )
            return True

        logger.error("Unsupported player_stat parameter: %s", param)
        return False

    def _is_upgrade_available_for_player(self, upgrade: dict[str, Any], player: Player) -> bool:
        """Validate character gating, one-time apply, and prerequisite chain."""
        required_char = str(upgrade.get("character", "any")).lower()
        if required_char not in {"any", player.character_id.lower()}:
            return False

        upgrade_id = str(upgrade.get("id", "")).strip()
        if upgrade_id and upgrade_id in player.applied_upgrade_ids:
            return False

        requires = upgrade.get("requires", [])
        if isinstance(requires, list):
            for req in requires:
                if str(req) not in player.applied_upgrade_ids:
                    return False

        return True
