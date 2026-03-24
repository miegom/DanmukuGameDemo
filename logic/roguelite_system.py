"""Roguelite upgrade pool and runtime application logic."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from core.logger import logger
from core.resource_mgr import ResourceManager
from logic.danmaku_system import EmissionOperator, MotionOperator, SwirlMotion
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
        """Draw random unique upgrades from the pool.

        Args:
            count: Number of options to draw.

        Returns:
            Randomly sampled upgrade list.
        """
        if count <= 0 or not self._pool:
            return []

        actual_count = min(count, len(self._pool))
        choices = self._rng.sample(self._pool, k=actual_count)
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

        try:
            weapon_group = player.get_weapon_group(target)
        except ValueError as exc:
            logger.error("Upgrade target error: %s", exc)
            return False

        upgrade_name = str(upgrade_dict.get("name", "unknown"))

        if upgrade_type == "emission":
            changed = self._apply_emission_upgrade(upgrade_dict, weapon_group.emission)
            if changed:
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

        logger.error("Unsupported motion type: %s", motion_name)
        return None

