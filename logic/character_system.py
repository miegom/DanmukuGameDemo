"""Character profile loading and selection helpers."""

from __future__ import annotations

from dataclasses import dataclass

from core.logger import logger
from core.resource_mgr import ResourceManager


@dataclass(frozen=True, slots=True)
class CharacterProfile:
    """Data-driven character combat and icon parameters."""

    char_id: str
    display_name: str
    basic_mode: str
    basic_bullet_count: int
    basic_bullet_spread: float
    basic_fire_rate: float
    basic_bullet_speed: float
    basic_bullet_lifetime: float
    basic_laser_interval: float
    basic_laser_width: float
    basic_laser_damage: int
    basic_laser_range: float
    spell_mode: str
    spell_duration: float
    spell_orb_count: int
    spell_orb_speed: float
    spell_orb_radius: float
    spell_orb_damage: int
    spell_orb_clear_radius: float
    spell_bullet_lifetime: float
    spell_laser_width_multiplier: float
    spell_laser_damage_multiplier: float
    icon_outer_color: tuple[int, int, int]
    icon_inner_color: tuple[int, int, int]
    pickup_attract_radius_multiplier: float
    pickup_attract_strength: float


def load_character_profiles(path: str = "assets/data/characters.json") -> dict[str, CharacterProfile]:
    """Load character profiles with safe fallbacks."""
    payload = ResourceManager.load_json(path)
    raw_list = payload.get("characters", []) if isinstance(payload, dict) else []
    if not isinstance(raw_list, list):
        raw_list = []

    profiles: dict[str, CharacterProfile] = {}
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        profile = _parse_profile(raw)
        if profile is not None:
            profiles[profile.char_id] = profile

    if "reimu" not in profiles:
        logger.warning("characters.json missing reimu; injecting built-in default.")
        profiles["reimu"] = _default_reimu_profile()

    if "morisa" not in profiles:
        logger.warning("characters.json missing morisa; injecting built-in default.")
        profiles["morisa"] = _default_morisa_profile()

    return profiles


def _parse_profile(raw: dict[str, object]) -> CharacterProfile | None:
    """Parse one profile dictionary into typed fields."""
    try:
        char_id = str(raw.get("id", "")).strip().lower()
        if not char_id:
            return None

        icon_outer = _parse_color(raw.get("icon_outer_color"), (220, 220, 220))
        icon_inner = _parse_color(raw.get("icon_inner_color"), (255, 255, 255))

        return CharacterProfile(
            char_id=char_id,
            display_name=str(raw.get("display_name", char_id)),
            basic_mode=str(raw.get("basic_mode", "danmaku")),
            basic_bullet_count=max(1, int(raw.get("basic_bullet_count", 1))),
            basic_bullet_spread=float(raw.get("basic_bullet_spread", 0.0)),
            basic_fire_rate=max(0.0, float(raw.get("basic_fire_rate", 0.0))),
            basic_bullet_speed=max(0.0, float(raw.get("basic_bullet_speed", 0.0))),
            basic_bullet_lifetime=max(0.0, float(raw.get("basic_bullet_lifetime", 2.2))),
            basic_laser_interval=max(0.01, float(raw.get("basic_laser_interval", 1.0))),
            basic_laser_width=max(1.0, float(raw.get("basic_laser_width", 14.0))),
            basic_laser_damage=max(1, int(raw.get("basic_laser_damage", 6))),
            basic_laser_range=max(80.0, float(raw.get("basic_laser_range", 860.0))),
            spell_mode=str(raw.get("spell_mode", "burst")),
            spell_duration=max(0.0, float(raw.get("spell_duration", 0.0))),
            spell_orb_count=max(1, int(raw.get("spell_orb_count", 5))),
            spell_orb_speed=max(1.0, float(raw.get("spell_orb_speed", 220.0))),
            spell_orb_radius=max(2.0, float(raw.get("spell_orb_radius", 18.0))),
            spell_orb_damage=max(1, int(raw.get("spell_orb_damage", 15))),
            spell_orb_clear_radius=max(2.0, float(raw.get("spell_orb_clear_radius", 30.0))),
            spell_bullet_lifetime=max(0.0, float(raw.get("spell_bullet_lifetime", 3.0))),
            spell_laser_width_multiplier=max(1.0, float(raw.get("spell_laser_width_multiplier", 2.2))),
            spell_laser_damage_multiplier=max(1.0, float(raw.get("spell_laser_damage_multiplier", 2.5))),
            icon_outer_color=icon_outer,
            icon_inner_color=icon_inner,
            pickup_attract_radius_multiplier=max(0.0, float(raw.get("pickup_attract_radius_multiplier", 2.0))),
            pickup_attract_strength=max(0.0, float(raw.get("pickup_attract_strength", 66.0))),
        )
    except (TypeError, ValueError):
        return None


def _parse_color(raw: object, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """Parse RGB list safely."""
    if not isinstance(raw, list) or len(raw) != 3:
        return fallback
    try:
        r = int(raw[0])
        g = int(raw[1])
        b = int(raw[2])
    except (TypeError, ValueError):
        return fallback
    return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def _default_reimu_profile() -> CharacterProfile:
    """Fallback profile for Reimu."""
    return CharacterProfile(
        char_id="reimu",
        display_name="灵梦",
        basic_mode="danmaku",
        basic_bullet_count=5,
        basic_bullet_spread=0.52,
        basic_fire_rate=11.0,
        basic_bullet_speed=260.0,
        basic_bullet_lifetime=2.8,
        basic_laser_interval=1.0,
        basic_laser_width=12.0,
        basic_laser_damage=6,
        basic_laser_range=860.0,
        spell_mode="orbs",
        spell_duration=0.0,
        spell_orb_count=5,
        spell_orb_speed=240.0,
        spell_orb_radius=18.0,
        spell_orb_damage=16,
        spell_orb_clear_radius=34.0,
        spell_bullet_lifetime=3.0,
        spell_laser_width_multiplier=2.2,
        spell_laser_damage_multiplier=2.5,
        icon_outer_color=(220, 50, 70),
        icon_inner_color=(255, 255, 255),
        pickup_attract_radius_multiplier=2.0,
        pickup_attract_strength=66.0,
    )


def _default_morisa_profile() -> CharacterProfile:
    """Fallback profile for Morisa."""
    return CharacterProfile(
        char_id="morisa",
        display_name="魔理沙",
        basic_mode="laser",
        basic_bullet_count=1,
        basic_bullet_spread=0.0,
        basic_fire_rate=1.0,
        basic_bullet_speed=260.0,
        basic_bullet_lifetime=2.0,
        basic_laser_interval=1.0,
        basic_laser_width=16.0,
        basic_laser_damage=10,
        basic_laser_range=980.0,
        spell_mode="laser_boost",
        spell_duration=5.0,
        spell_orb_count=1,
        spell_orb_speed=200.0,
        spell_orb_radius=12.0,
        spell_orb_damage=10,
        spell_orb_clear_radius=20.0,
        spell_bullet_lifetime=3.0,
        spell_laser_width_multiplier=2.8,
        spell_laser_damage_multiplier=2.8,
        icon_outer_color=(250, 220, 50),
        icon_inner_color=(20, 20, 20),
        pickup_attract_radius_multiplier=2.0,
        pickup_attract_strength=66.0,
    )

