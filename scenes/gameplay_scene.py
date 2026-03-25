"""Core playable scene with decoupled logic and rendering paths."""

from __future__ import annotations

from itertools import repeat
from typing import Any

import numpy as np
import pygame

from core.camera import Camera
from core.resource_mgr import ResourceManager
from logic.character_system import CharacterProfile, load_character_profiles
from logic.danmaku_system import (
    DanmakuGroup,
    DiscreteShape,
    EmissionOperator,
    HomingMotion,
    LinearMotion,
)
from logic.entity import Enemy, ExpOrb, Player
from logic.level_system import WaveManager
from logic.roguelite_system import UpgradeManager
from scenes.base_scene import BaseScene


class GameplayScene(BaseScene):
    """Main gameplay scene with vectorized collision and character-specific attacks."""

    def __init__(self, context: dict[str, Any]) -> None:
        """Initialize gameplay state, entities, and render resources."""
        super().__init__(context)

        if "upgrade_manager" not in self.context:
            self.context["upgrade_manager"] = UpgradeManager()

        # Always start a fresh wave manager when creating a new gameplay run.
        # Upgrade resume path reuses the existing GameplayScene instance, so this
        # does not reset progress mid-run.
        self.context["wave_manager"] = WaveManager(
            random_seed=int(context.get("seed", 20260324)),
        )

        profiles = load_character_profiles()
        selected_character = str(self.context.get("selected_character_id", "reimu")).lower()
        self._character_profile: CharacterProfile = profiles.get(selected_character, profiles["reimu"])

        self._base_reimu_fire_rate: float = float(self._character_profile.basic_fire_rate)
        self._base_reimu_bullet_speed: float = float(self._character_profile.basic_bullet_speed)
        self._base_reimu_bullet_lifetime: float = float(self._character_profile.basic_bullet_lifetime)
        self._base_reimu_count: int = int(self._character_profile.basic_bullet_count)
        self._base_morisa_laser_interval: float = float(self._character_profile.basic_laser_interval)
        self._base_morisa_laser_width: float = float(self._character_profile.basic_laser_width)

        self.player = Player(x=0.0, y=0.0)
        self.player.character_id = self._character_profile.char_id
        self._configure_player_loadout(self._character_profile)
        self.camera = Camera()

        self._screen_width: int = int(context.get("screen_width", 1280))
        self._screen_height: int = int(context.get("screen_height", 720))
        self.enemies: list[Enemy] = []
        self.exp_orbs: list[ExpOrb] = []
        self._wave_manager: WaveManager = self.context["wave_manager"]

        self.map_bounds: tuple[float, float, float, float] = (-2400.0, 2400.0, -1800.0, 1800.0)
        self.enemy_speed: float = 60.0
        self.camera_smooth: float = 6.0
        self.time_value: float = 0.0
        self.frame_timer: int = 0
        self.frame_to_seconds: float = 1.0 / 60.0
        self.collision_grace_seconds: float = 0.8
        self.score: float = 0.0
        self._score_kill: int = 0
        self._score_survival: float = 0.0
        self._score_upgrade: int = 0
        self._score_bullet_clear: int = 0
        self._score_point_pickup: int = 0

        self._input_x: float = 0.0
        self._input_y: float = 0.0

        self._grid_step: int = 64
        self._enemy_bullet_hit_radius_sq: float = self.player.radius ** 2
        self._player_bullet_hit_radius: float = 4.0
        self._exp_pickup_radius: float = 26.0
        self._enemy_hit_damage: int = 2
        self._max_active_enemies: int = 8
        self._post_hit_invuln_seconds: float = 3.0
        self._player_invuln_remaining: float = 0.0

        self._enemy_death_bloom = DanmakuGroup(
            shape=DiscreteShape(count=1, spread=0.0, base_angle=0.0),
            emission=EmissionOperator(fire_rate=0.0, speed=0.0, spin_speed=0.0),
            motions=[LinearMotion()],
            max_bullets=4096,
            bounds=(-4000.0, 4000.0, -3200.0, 3200.0),
            max_lifetime=2.6,
        )

        self._player_bullet_sprite = pygame.Surface((6, 6), pygame.SRCALPHA)
        self._player_bullet_sprite.fill((80, 235, 255))
        self._player_spell_sprite = pygame.Surface((10, 10), pygame.SRCALPHA)
        self._player_spell_sprite.fill((255, 245, 120))
        self._enemy_bullet_sprite = pygame.Surface((6, 6), pygame.SRCALPHA)
        self._enemy_bullet_sprite.fill((255, 90, 120))
        self._hud_font: pygame.font.Font | None = None
        self._score_font: pygame.font.Font | None = None
        self._score_overlay: pygame.Surface | None = None

        self._basic_laser_cooldown: float = 0.0
        self._spell_boost_remaining: float = 0.0
        self._laser_visual_timer: float = 0.0
        self._laser_visual_start: tuple[float, float] = (0.0, 0.0)
        self._laser_visual_end: tuple[float, float] = (0.0, 0.0)
        self._laser_visual_width: int = 2
        self._laser_visual_color: tuple[int, int, int] = (255, 240, 120)
        self._laser_effects: list[dict[str, Any]] = []
        self._spell_cast_flash: float = 0.0
        self._reimu_homing_motion: HomingMotion | None = None
        self._reimu_homing_base_accel: float = 420.0
        self._reimu_homing_base_duration: float = 0.35
        self._reimu_spell_base_life: float = 2.2
        self._reimu_spell_homing_radius: float = 760.0
        self._reimu_spell_homing_accel: float = 1280.0
        self._reimu_spell_homing_duration: float = 1.4
        self._basic_sprite_size: int = self._player_bullet_sprite.get_width()
        self._reimu_spell_orbs: list[dict[str, Any]] = []

        ui_config = ResourceManager.load_json("assets/data/ui.json")
        text_map = ui_config.get("texts", {}) if isinstance(ui_config, dict) else {}
        self._ui_texts = text_map if isinstance(text_map, dict) else {}
        self._rng = np.random.default_rng(int(context.get("seed", 20260324)) + 1007)

        self.context["player"] = self.player
        self.context["gameplay_scene"] = self

    def process_input(
        self,
        events: list[pygame.event.Event],
        keys: pygame.key.ScancodeWrapper,
    ) -> None:
        """Cache movement and mouse-control state."""
        self._input_x = float(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - float(
            keys[pygame.K_a] or keys[pygame.K_LEFT]
        )
        self._input_y = float(keys[pygame.K_s] or keys[pygame.K_DOWN]) - float(
            keys[pygame.K_w] or keys[pygame.K_UP]
        )
        self.player.is_focus_mode = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])

        mouse_buttons = pygame.mouse.get_pressed()
        self.player.is_firing = bool(mouse_buttons[0])

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if self._is_spell_cast_busy():
                    continue
                consumed = self.player.consume_one_spell_charge()
                if consumed > 0:
                    self._spell_cast_flash = 0.24
                    self._activate_spell_card(consumed)

        mx, my = pygame.mouse.get_pos()
        world_mx = mx + self.camera.x
        world_my = my + self.camera.y
        self.player.target_angle = float(np.arctan2(world_my - self.player.y, world_mx - self.player.x))

    def update(self, dt: float) -> None:
        """Run world simulation step and resolve collisions."""
        if dt <= 0.0:
            return

        self.frame_timer += 1
        frame_time = float(self.frame_timer) * self.frame_to_seconds

        self.time_value += dt
        self._player_invuln_remaining = max(0.0, self._player_invuln_remaining - dt)
        self._spell_cast_flash = max(0.0, self._spell_cast_flash - dt)
        self._score_survival += dt * 10.0
        self.score = (
            float(self._score_kill)
            + self._score_survival
            + float(self._score_upgrade)
            + float(self._score_bullet_clear)
            + float(self._score_point_pickup)
        )
        self.context["score"] = int(self.score)
        self._update_laser_effects(dt)

        self.player.update_movement(
            dx=self._input_x,
            dy=self._input_y,
            dt=dt,
            boundaries=self.map_bounds,
        )
        self._update_camera(dt)

        spawned_enemies = self._wave_manager.update_with_cap(
            dt=dt,
            player_x=self.player.x,
            player_y=self.player.y,
            current_enemy_count=len(self.enemies),
            max_active_enemies=self._wave_manager.get_spawn_cap_for_wave(self._wave_manager.current_wave_number),
        )
        if spawned_enemies:
            self.enemies.extend(spawned_enemies)

        for enemy in self.enemies:
            self._move_enemy_with_ai(enemy, dt)

        self._update_group_homing_snapshots()

        self._sync_basic_attack_tuning()
        self.player.update_attack(t=frame_time, dt=dt)

        if self._character_profile.basic_mode == "laser":
            self._update_morisa_laser(dt)
        self._update_reimu_orbs(dt)

        for enemy in self.enemies:
            enemy.update_attack(t=frame_time, px=self.player.x, py=self.player.y)
            self._update_enemy_attack(enemy, dt=dt)

        self._enemy_death_bloom.update(
            t=frame_time,
            ex=0.0,
            ey=0.0,
            px=self.player.x,
            py=self.player.y,
        )

        self._resolve_player_bullet_hits()
        self._collect_pickups()

        if self.player.level_up:
            from scenes.upgrade_scene import UpgradeScene

            self._score_upgrade += 150

            self.context["player"] = self.player
            self.context["gameplay_scene"] = self
            self.context["previous_gameplay_scene"] = self
            self.player.level_up = False
            self.switch_to(UpgradeScene)
            return

        if self.time_value >= self.collision_grace_seconds:
            if self._check_enemy_bullet_collision() or self._check_enemy_contact_collision():
                self._apply_player_hit()

            if self.player.current_hp <= 0:
                from scenes.gameover_scene import GameOverScene

                self.context.pop("gameplay_scene", None)
                self.context.pop("previous_gameplay_scene", None)
                self.switch_to(GameOverScene)

    def draw(self, screen: pygame.Surface) -> None:
        """Render map, entities, bullets, spell effects, and HUD."""
        self._screen_width, self._screen_height = screen.get_size()
        screen.fill((8, 10, 16))

        self._draw_grid(screen)
        self._draw_entities(screen)
        self._draw_all_bullets(screen)
        self._draw_spell_effects(screen)
        self._draw_exp_orbs(screen)
        self._draw_scoreboard(screen)
        self._draw_hud(screen)

    def _configure_player_loadout(self, profile: CharacterProfile) -> None:
        """Set player weapons according to selected character profile."""
        if profile.basic_mode == "danmaku":
            self.player.basic_weapon = DanmakuGroup(
                shape=DiscreteShape(
                    count=profile.basic_bullet_count,
                    spread=profile.basic_bullet_spread,
                    base_angle=-np.pi / 2.0,
                ),
                emission=EmissionOperator(
                    fire_rate=profile.basic_fire_rate,
                    speed=profile.basic_bullet_speed,
                    spin_speed=0.0,
                ),
                motions=[LinearMotion()],
                max_bullets=4096,
                bounds=(-2800.0, 2800.0, -2200.0, 2200.0),
                max_lifetime=max(0.2, float(profile.basic_bullet_lifetime)),
            )
        else:
            self.player.basic_weapon = DanmakuGroup(
                shape=DiscreteShape(count=1, spread=0.0, base_angle=-np.pi / 2.0),
                emission=EmissionOperator(fire_rate=0.0, speed=profile.basic_bullet_speed, spin_speed=0.0),
                motions=[LinearMotion()],
                max_bullets=512,
                bounds=(-2800.0, 2800.0, -2200.0, 2200.0),
                max_lifetime=max(0.2, float(profile.basic_bullet_lifetime)),
            )

        self.player.spell_card = DanmakuGroup(
            shape=DiscreteShape(count=1, spread=0.0, base_angle=-np.pi / 2.0),
            emission=EmissionOperator(fire_rate=0.0, speed=0.0, spin_speed=0.0),
            motions=[LinearMotion()],
            max_bullets=512,
            bounds=(-2800.0, 2800.0, -2200.0, 2200.0),
            max_lifetime=max(0.2, float(profile.spell_bullet_lifetime)),
        )

    def _sync_basic_attack_tuning(self) -> None:
        """Synchronize character basic-attack runtime parameters from upgrades."""
        if self.player.character_id == "reimu":
            shape = self.player.basic_weapon.shape
            if isinstance(shape, DiscreteShape):
                shape.count = max(1, self._base_reimu_count + self.player.tuning.reimu_basic_extra_count)

            interval_mul = max(0.2, self.player.tuning.reimu_basic_interval_mul)
            self.player.basic_weapon.emission.fire_rate = self._base_reimu_fire_rate / interval_mul
            self.player.basic_weapon.emission.speed = (
                self._base_reimu_bullet_speed * max(0.2, self.player.tuning.reimu_basic_speed_mul)
            )

            size_mul = max(0.6, self.player.tuning.reimu_basic_size_mul)
            sprite_size = max(4, int(round(6.0 * size_mul)))
            if sprite_size != self._basic_sprite_size:
                self._basic_sprite_size = sprite_size
                self._player_bullet_sprite = pygame.Surface((sprite_size, sprite_size), pygame.SRCALPHA)
                self._player_bullet_sprite.fill((80, 235, 255))
            self._player_bullet_hit_radius = 4.0 * size_mul
            self.player.basic_weapon.max_lifetime = max(0.6, self._base_reimu_bullet_lifetime)
            self._sync_reimu_homing_motion()
            return

        self._player_bullet_hit_radius = 4.0
        self.player.basic_weapon.max_lifetime = max(0.2, float(self._character_profile.basic_bullet_lifetime))

    def _sync_reimu_homing_motion(self) -> None:
        """Attach/update/remove Reimu basic homing behavior by upgrade tier."""
        radius = max(0.0, self.player.tuning.reimu_basic_homing_radius)
        accel = max(0.0, self.player.tuning.reimu_basic_homing_accel)
        duration = max(0.0, self.player.tuning.reimu_basic_homing_duration)

        if radius <= 0.0:
            self.player.basic_weapon.motions = [
                motion for motion in self.player.basic_weapon.motions if not isinstance(motion, HomingMotion)
            ]
            self._reimu_homing_motion = None
            return

        # Homing radius unlock should be immediately effective even before accel upgrades.
        effective_accel = accel if accel > 0.0 else self._reimu_homing_base_accel
        effective_duration = duration if duration > 0.0 else self._reimu_homing_base_duration

        if self._reimu_homing_motion is None:
            self._reimu_homing_motion = HomingMotion(
                acceleration=effective_accel,
                max_distance=radius,
                lock_duration=effective_duration,
            )
            self.player.basic_weapon.motions.append(self._reimu_homing_motion)
            return

        self._reimu_homing_motion.set_homing_params(
            radius=radius,
            acceleration=effective_accel,
            lock_duration=effective_duration,
        )

    def _activate_spell_card(self, charges: int) -> None:
        """Activate character-specific spell card behavior."""
        if charges <= 0 or self._is_spell_cast_busy():
            return

        if self._character_profile.spell_mode == "orbs":
            self._spawn_reimu_orbs()
            return

        if self._character_profile.spell_mode == "laser_boost":
            self._spell_boost_remaining = self._character_profile.spell_duration

    def _is_spell_cast_busy(self) -> bool:
        """Return whether current character is still in an active spell phase."""
        if self._character_profile.spell_mode == "orbs":
            return bool(self._reimu_spell_orbs)
        if self._character_profile.spell_mode == "laser_boost":
            return self._spell_boost_remaining > 0.0
        return False

    def _spawn_reimu_orbs(self) -> None:
        """Spawn Reimu giant yin-yang orbs around the player."""
        self._reimu_spell_orbs.clear()
        count = max(1, self._character_profile.spell_orb_count + self.player.tuning.reimu_spell_extra_orbs)
        size_mul = max(0.6, self.player.tuning.reimu_spell_size_mul)
        life_mul = max(0.6, self.player.tuning.reimu_spell_life_mul)
        colors = [
            (255, 70, 70),
            (255, 180, 70),
            (240, 240, 90),
            (90, 220, 255),
            (210, 120, 255),
        ]
        base_radius = 44.0
        for index in range(count):
            theta = (2.0 * np.pi * index) / float(count)
            orb = {
                "x": self.player.x + np.cos(theta) * base_radius,
                "y": self.player.y + np.sin(theta) * base_radius,
                "vx": np.cos(theta) * self._character_profile.spell_orb_speed,
                "vy": np.sin(theta) * self._character_profile.spell_orb_speed,
                "radius": self._character_profile.spell_orb_radius * size_mul,
                "damage": self._character_profile.spell_orb_damage,
                "clear_radius": self._character_profile.spell_orb_clear_radius * size_mul,
                "color": colors[index % len(colors)],
                "life": self._reimu_spell_base_life * life_mul,
                "homing_lock": 0.0,
                "target_x": float(self.player.x),
                "target_y": float(self.player.y),
            }
            self._reimu_spell_orbs.append(orb)

    def _update_reimu_orbs(self, dt: float) -> None:
        """Update giant-orb movement, damage, and bullet-clearing."""
        if not self._reimu_spell_orbs:
            return

        enemy_x, enemy_y = self._enemy_position_arrays()
        for orb in self._reimu_spell_orbs:
            prev_x = float(orb["x"])
            prev_y = float(orb["y"])

            orb["homing_lock"] = max(0.0, float(orb.get("homing_lock", 0.0)) - dt)
            if float(orb["homing_lock"]) <= 0.0:
                self._try_acquire_orb_target(orb, enemy_x=enemy_x, enemy_y=enemy_y)
            elif enemy_x.size > 0:
                self._refresh_orb_target(orb, enemy_x=enemy_x, enemy_y=enemy_y)

            if float(orb["homing_lock"]) > 0.0:
                dx = float(orb["target_x"]) - prev_x
                dy = float(orb["target_y"]) - prev_y
                length = float(np.hypot(dx, dy))
                if length > 1.0e-6:
                    accel = self._reimu_spell_homing_accel * dt
                    orb["vx"] = float(orb["vx"]) + (dx / length) * accel
                    orb["vy"] = float(orb["vy"]) + (dy / length) * accel

            speed = self._character_profile.spell_orb_speed
            vel_len = float(np.hypot(float(orb["vx"]), float(orb["vy"])))
            if vel_len > 1.0e-6:
                orb["vx"] = (float(orb["vx"]) / vel_len) * speed
                orb["vy"] = (float(orb["vy"]) / vel_len) * speed

            orb["x"] = prev_x + float(orb["vx"]) * dt
            orb["y"] = prev_y + float(orb["vy"]) * dt
            orb["life"] = float(orb["life"]) - dt

            cleared = self._clear_enemy_bullets_along_segment(
                ax=prev_x,
                ay=prev_y,
                bx=float(orb["x"]),
                by=float(orb["y"]),
                radius=float(orb["clear_radius"]),
            )
            self._score_bullet_clear += cleared * 2
            self._damage_enemies_along_segment(
                ax=prev_x,
                ay=prev_y,
                bx=float(orb["x"]),
                by=float(orb["y"]),
                radius=float(orb["radius"]),
                damage=int(orb["damage"]),
            )

        self._reimu_spell_orbs = [
            orb
            for orb in self._reimu_spell_orbs
            if float(orb["life"]) > 0.0
            and -3200.0 < float(orb["x"]) < 3200.0
            and -2400.0 < float(orb["y"]) < 2400.0
        ]

    def _update_group_homing_snapshots(self) -> None:
        """Provide enemy snapshots for all homing motions in player groups."""
        enemy_x, enemy_y = self._enemy_position_arrays()
        for group in (self.player.basic_weapon, self.player.spell_card):
            for motion in group.motions:
                if isinstance(motion, HomingMotion):
                    motion.set_enemy_points(enemy_x=enemy_x, enemy_y=enemy_y)

    def _enemy_position_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        """Return enemy position arrays for vectorized homing queries."""
        if not self.enemies:
            return np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32)

        enemy_x = np.asarray([enemy.x for enemy in self.enemies], dtype=np.float32)
        enemy_y = np.asarray([enemy.y for enemy in self.enemies], dtype=np.float32)
        return enemy_x, enemy_y

    def _try_acquire_orb_target(self, orb: dict[str, Any], enemy_x: np.ndarray, enemy_y: np.ndarray) -> None:
        """Acquire orb target if an enemy enters orb homing radius."""
        if enemy_x.size == 0:
            return

        ox = np.float32(float(orb["x"]))
        oy = np.float32(float(orb["y"]))
        dx = enemy_x - ox
        dy = enemy_y - oy
        dist_sq = (dx * dx) + (dy * dy)
        radius_sq = np.float32(self._reimu_spell_homing_radius * self._reimu_spell_homing_radius)
        in_range = dist_sq <= radius_sq
        if not np.any(in_range):
            return

        masked = np.where(in_range, dist_sq, np.float32(np.inf))
        index = int(np.argmin(masked))
        orb["target_x"] = float(enemy_x[index])
        orb["target_y"] = float(enemy_y[index])
        orb["homing_lock"] = self._reimu_spell_homing_duration

    def _refresh_orb_target(self, orb: dict[str, Any], enemy_x: np.ndarray, enemy_y: np.ndarray) -> None:
        """Update orb lock target toward nearest enemy around previous lock point."""
        if enemy_x.size == 0:
            return

        tx = np.float32(float(orb.get("target_x", orb["x"])))
        ty = np.float32(float(orb.get("target_y", orb["y"])))
        dx = enemy_x - tx
        dy = enemy_y - ty
        index = int(np.argmin((dx * dx) + (dy * dy)))
        orb["target_x"] = float(enemy_x[index])
        orb["target_y"] = float(enemy_y[index])

    def _update_morisa_laser(self, dt: float) -> None:
        """Fire Morisa laser fan with short-lived diffusion visuals."""
        if self._spell_boost_remaining > 0.0:
            self._spell_boost_remaining = max(0.0, self._spell_boost_remaining - dt)

        if self._basic_laser_cooldown > 0.0:
            self._basic_laser_cooldown = max(0.0, self._basic_laser_cooldown - dt)

        if not self.player.is_firing or self._basic_laser_cooldown > 0.0:
            self._laser_visual_timer = max(0.0, self._laser_visual_timer - dt)
            return

        boost = self._spell_boost_remaining > 0.0
        interval_mul = max(0.25, self.player.tuning.morisa_basic_interval_mul)
        interval_scale = 0.2 if boost else 1.0
        if boost:
            interval_scale /= max(0.5, self.player.tuning.morisa_spell_fire_rate_mul)
        self._basic_laser_cooldown = self._base_morisa_laser_interval * interval_mul * interval_scale

        width = self._base_morisa_laser_width * max(0.6, self.player.tuning.morisa_basic_width_mul)
        damage = self._character_profile.basic_laser_damage
        color = (255, 235, 120)
        if boost:
            width *= self._character_profile.spell_laser_width_multiplier
            width *= max(1.0, self.player.tuning.morisa_spell_extra_width_mul)
            damage = int(damage * self._character_profile.spell_laser_damage_multiplier)
            color = (255, 170, 60)

        beam_count = 1 + max(0, self.player.tuning.morisa_basic_extra_lasers)
        if boost:
            beam_count += max(0, self.player.tuning.morisa_spell_extra_lasers)
        spread = np.float32(0.22)
        if beam_count <= 1:
            angle_offsets = np.asarray([0.0], dtype=np.float32)
        else:
            angle_offsets = np.linspace(
                -0.5 * spread,
                0.5 * spread,
                num=beam_count,
                endpoint=True,
                dtype=np.float32,
            )

        ax = self.player.x
        ay = self.player.y
        beam_range = float(max(self._screen_width, self._screen_height) * 2.4)

        for offset in angle_offsets.tolist():
            angle = self.player.target_angle + float(offset)
            bx = ax + np.cos(angle) * beam_range
            by = ay + np.sin(angle) * beam_range

            self._damage_enemies_along_segment(ax=ax, ay=ay, bx=bx, by=by, radius=0.5 * width, damage=damage)
            cleared = self._clear_enemy_bullets_along_segment(ax=ax, ay=ay, bx=bx, by=by, radius=0.5 * width)
            self._score_bullet_clear += cleared * 2
            self._spawn_laser_effect(
                ax=ax,
                ay=ay,
                bx=bx,
                by=by,
                width_start=width * 0.55,
                width_end=width * 1.2,
                color=color,
                life=0.12,
            )

        self._laser_visual_start = (ax, ay)
        self._laser_visual_end = (bx, by)
        self._laser_visual_width = max(2, int(width))
        self._laser_visual_color = color
        self._laser_visual_timer = 0.04

    def _spawn_laser_effect(
        self,
        ax: float,
        ay: float,
        bx: float,
        by: float,
        width_start: float,
        width_end: float,
        color: tuple[int, int, int],
        life: float,
    ) -> None:
        """Create one short-lived laser trail effect entry."""
        self._laser_effects.append(
            {
                "ax": ax,
                "ay": ay,
                "bx": bx,
                "by": by,
                "width_start": max(1.0, width_start),
                "width_end": max(1.0, width_end),
                "color": color,
                "life": max(0.02, life),
                "max_life": max(0.02, life),
            }
        )

    def _update_laser_effects(self, dt: float) -> None:
        """Decay and compact transient laser effects."""
        if not self._laser_effects:
            return

        for effect in self._laser_effects:
            effect["life"] = float(effect["life"]) - dt

        self._laser_effects = [effect for effect in self._laser_effects if float(effect["life"]) > 0.0]

    def _spawn_laser_effect_buffer(
        self, ax: float, ay: float, bx: float, by: float, width: float, color: tuple[int, int, int]
    ) -> None:
        """Create visual buffer for laser effect during spell boost."""
        head_size = max(4, int(width * 0.5))
        tail_size = max(4, int(width * 0.2))
        segment_count = max(2, int(np.hypot(bx - ax, by - ay) / 20.0))

        for i in range(segment_count):
            t = (i + 1) / segment_count
            x_pos = ax + (bx - ax) * t
            y_pos = ay + (by - ay) * t
            size = head_size if i == segment_count - 1 else tail_size
            self._laser_effects.append({"x": x_pos, "y": y_pos, "size": size, "color": color, "life": 0.5})

    def _damage_enemies_along_segment(
        self,
        ax: float,
        ay: float,
        bx: float,
        by: float,
        radius: float,
        damage: int,
    ) -> None:
        """Apply line-segment damage to enemies using vectorized distance checks."""
        if not self.enemies or damage <= 0:
            return

        enemy_x = np.asarray([enemy.x for enemy in self.enemies], dtype=np.float32)
        enemy_y = np.asarray([enemy.y for enemy in self.enemies], dtype=np.float32)
        enemy_r = np.asarray([enemy.radius for enemy in self.enemies], dtype=np.float32)

        dist_sq = self._segment_distance_sq(enemy_x, enemy_y, ax=ax, ay=ay, bx=bx, by=by)
        hit_sq = (enemy_r + np.float32(radius)) ** 2
        hit_mask = dist_sq <= hit_sq
        if not np.any(hit_mask):
            return

        for index, is_hit in enumerate(hit_mask.tolist()):
            if is_hit:
                self.enemies[index].hp -= damage

    def _clear_enemy_bullets_along_segment(self, ax: float, ay: float, bx: float, by: float, radius: float) -> int:
        """Erase enemy bullets close to a line segment and return clear count."""
        if not self.enemies and self._enemy_death_bloom.pool.active_count <= 0:
            return 0

        radius_sq = np.float32(radius * radius)
        cleared_total = 0
        for enemy in self.enemies:
            pool = enemy.danmaku.pool
            active = pool.active_count
            if active <= 0:
                continue

            px = pool.x[:active]
            py = pool.y[:active]
            dist_sq = self._segment_distance_sq(px, py, ax=ax, ay=ay, bx=bx, by=by)
            keep_mask = dist_sq > radius_sq
            if np.any(~keep_mask):
                cleared_total += int(np.count_nonzero(~keep_mask))
                pool.filter_active(keep_mask.astype(np.bool_))

        death_pool = self._enemy_death_bloom.pool
        death_active = death_pool.active_count
        if death_active > 0:
            dist_sq = self._segment_distance_sq(
                death_pool.x[:death_active],
                death_pool.y[:death_active],
                ax=ax,
                ay=ay,
                bx=bx,
                by=by,
            )
            keep_mask = dist_sq > radius_sq
            if np.any(~keep_mask):
                cleared_total += int(np.count_nonzero(~keep_mask))
                death_pool.filter_active(keep_mask.astype(np.bool_))

        return cleared_total

    def _get_nearest_enemy(self) -> Enemy | None:
        """Return nearest enemy to player or None."""
        if not self.enemies:
            return None
        return min(
            self.enemies,
            key=lambda enemy: (enemy.x - self.player.x) ** 2 + (enemy.y - self.player.y) ** 2,
        )

    @staticmethod
    def _segment_distance_sq(
        px: np.ndarray,
        py: np.ndarray,
        ax: float,
        ay: float,
        bx: float,
        by: float,
    ) -> np.ndarray:
        """Return squared distance from many points to segment AB."""
        abx = np.float32(bx - ax)
        aby = np.float32(by - ay)
        apx = px - np.float32(ax)
        apy = py - np.float32(ay)
        denom = np.float32((abx * abx) + (aby * aby))
        if denom <= np.float32(1.0e-6):
            return (apx * apx) + (apy * apy)

        t = (apx * abx + apy * aby) / denom
        t = np.clip(t, np.float32(0.0), np.float32(1.0))
        cx = np.float32(ax) + t * abx
        cy = np.float32(ay) + t * aby
        dx = px - cx
        dy = py - cy
        return (dx * dx) + (dy * dy)

    def _update_camera(self, dt: float) -> None:
        """Smoothly follow player while keeping camera within map bounds."""
        target_x = self.player.x - (self._screen_width * 0.5)
        target_y = self.player.y - (self._screen_height * 0.5)

        follow_alpha = min(1.0, self.camera_smooth * dt)
        self.camera.x += (target_x - self.camera.x) * follow_alpha
        self.camera.y += (target_y - self.camera.y) * follow_alpha

        x_min, x_max, y_min, y_max = self.map_bounds
        max_cam_x = max(x_min, x_max - self._screen_width)
        max_cam_y = max(y_min, y_max - self._screen_height)
        self.camera.x = max(x_min, min(max_cam_x, self.camera.x))
        self.camera.y = max(y_min, min(max_cam_y, self.camera.y))

    def _move_enemy_with_ai(self, enemy: Enemy, dt: float) -> None:
        """Move one enemy using its configured AI mode."""
        delta = np.asarray([self.player.x - enemy.x, self.player.y - enemy.y], dtype=np.float32)
        distance = float(np.linalg.norm(delta))
        if distance <= 1.0e-6:
            return

        direction = delta / np.float32(distance)
        tangent = np.asarray([-direction[1], direction[0]], dtype=np.float32)
        speed = max(10.0, enemy.move_speed)

        if enemy.ai_mode == "kite":
            move_dir = direction if distance > enemy.preferred_distance else -direction
            velocity = move_dir
        elif enemy.ai_mode == "charger":
            velocity = direction * np.float32(enemy.dash_speed_multiplier if distance <= enemy.dash_trigger_distance else 1.0)
        elif enemy.ai_mode == "kite_dodge":
            base = direction if distance > enemy.preferred_distance else -direction
            dodge = tangent * np.float32(np.sin(self.time_value * 4.5) * 0.55)
            velocity = base + dodge
            norm = float(np.linalg.norm(velocity))
            if norm > 1.0e-6:
                velocity /= np.float32(norm)
        else:
            velocity = direction

        enemy.x += float(velocity[0]) * speed * dt
        enemy.y += float(velocity[1]) * speed * dt

    def _update_enemy_attack(self, enemy: Enemy, dt: float) -> None:
        """Run burst-shoot state machine for one enemy."""
        if enemy.burst_waves <= 0:
            return

        enemy.attack_state_timer -= dt
        if enemy.attack_waves_left <= 0:
            if enemy.attack_state_timer > 0.0:
                return
            enemy.attack_waves_left = enemy.burst_waves
            enemy.attack_state_timer = 0.0

        if enemy.attack_state_timer > 0.0:
            return

        self._emit_enemy_fan(enemy)
        enemy.attack_waves_left -= 1
        enemy.attack_state_timer = enemy.burst_cooldown if enemy.attack_waves_left <= 0 else enemy.burst_interval

    def _emit_enemy_fan(self, enemy: Enemy) -> None:
        """Emit one fan burst directly into enemy bullet pool."""
        base_angle = float(np.arctan2(self.player.y - enemy.y, self.player.x - enemy.x))
        count = max(1, enemy.burst_fan_count)
        if count == 1:
            angles = np.asarray([base_angle], dtype=np.float32)
        else:
            angles = np.linspace(
                base_angle - (0.5 * enemy.burst_spread),
                base_angle + (0.5 * enemy.burst_spread),
                num=count,
                endpoint=True,
                dtype=np.float32,
            )

        speed = np.float32(max(0.0, enemy.burst_bullet_speed))
        x_batch = np.full(count, np.float32(enemy.x), dtype=np.float32)
        y_batch = np.full(count, np.float32(enemy.y), dtype=np.float32)
        vx_batch = np.cos(angles).astype(np.float32, copy=False) * speed
        vy_batch = np.sin(angles).astype(np.float32, copy=False) * speed
        enemy.danmaku.pool.spawn_batch(x_batch, y_batch, vx_batch, vy_batch)

    def _emit_enemy_death_bloom(self, enemy: Enemy) -> None:
        """Emit ring bullets when a death-bloom enemy is defeated."""
        rings = max(0, enemy.death_bloom_rings)
        if rings <= 0:
            return

        for ring_index in range(rings):
            count = 8 + (ring_index * 4)
            speed = np.float32(120.0 + (ring_index * 32.0))
            angles = np.linspace(0.0, 2.0 * np.pi, num=count, endpoint=False, dtype=np.float32)
            x_batch = np.full(count, np.float32(enemy.x), dtype=np.float32)
            y_batch = np.full(count, np.float32(enemy.y), dtype=np.float32)
            vx_batch = np.cos(angles).astype(np.float32, copy=False) * speed
            vy_batch = np.sin(angles).astype(np.float32, copy=False) * speed
            self._enemy_death_bloom.pool.spawn_batch(x_batch, y_batch, vx_batch, vy_batch)

    def _check_enemy_bullet_collision(self) -> bool:
        """Vectorized collision test between player and all enemy bullets."""
        enemy_x_arrays = [enemy.danmaku.pool.x[:enemy.danmaku.pool.active_count] for enemy in self.enemies]
        enemy_y_arrays = [enemy.danmaku.pool.y[:enemy.danmaku.pool.active_count] for enemy in self.enemies]
        death_pool = self._enemy_death_bloom.pool
        if death_pool.active_count > 0:
            enemy_x_arrays.append(death_pool.x[:death_pool.active_count])
            enemy_y_arrays.append(death_pool.y[:death_pool.active_count])

        active_x_arrays = [arr for arr in enemy_x_arrays if arr.size > 0]
        active_y_arrays = [arr for arr in enemy_y_arrays if arr.size > 0]
        if not active_x_arrays or not active_y_arrays:
            return False

        bullets_x = np.concatenate(active_x_arrays)
        bullets_y = np.concatenate(active_y_arrays)

        dx = bullets_x - np.float32(self.player.x)
        dy = bullets_y - np.float32(self.player.y)
        dist_sq = (dx * dx) + (dy * dy)
        return bool(np.any(dist_sq < np.float32(self._enemy_bullet_hit_radius_sq)))

    def _check_enemy_contact_collision(self) -> bool:
        """Detect body-contact collision between player and enemies."""
        if not self.enemies:
            return False

        enemy_x = np.asarray([enemy.x for enemy in self.enemies], dtype=np.float32)
        enemy_y = np.asarray([enemy.y for enemy in self.enemies], dtype=np.float32)
        enemy_r = np.asarray([enemy.radius for enemy in self.enemies], dtype=np.float32)

        dx = enemy_x - np.float32(self.player.x)
        dy = enemy_y - np.float32(self.player.y)
        dist_sq = (dx * dx) + (dy * dy)
        hit_sq = (enemy_r + np.float32(self.player.hitbox_radius)) ** 2
        return bool(np.any(dist_sq <= hit_sq))

    def _apply_player_hit(self) -> None:
        """Apply one player hit with invulnerability and instant spell reload."""
        if self._player_invuln_remaining > 0.0:
            return

        self.player.current_hp = max(0, self.player.current_hp - 1)
        self.player.add_drop_spell_stock(1)
        self.player.spell_cooldown = 0.0
        self._player_invuln_remaining = self._post_hit_invuln_seconds

    def _resolve_player_bullet_hits(self) -> None:
        """Apply vectorized player-bullet hits and clean up dead enemies."""
        if not self.enemies:
            return

        enemy_damage = np.zeros(len(self.enemies), dtype=np.int32)
        enemy_x = np.asarray([enemy.x for enemy in self.enemies], dtype=np.float32)
        enemy_y = np.asarray([enemy.y for enemy in self.enemies], dtype=np.float32)
        enemy_r = np.asarray([enemy.radius for enemy in self.enemies], dtype=np.float32)
        hit_radius_sq = (enemy_r + np.float32(self._player_bullet_hit_radius)) ** 2

        for group in (self.player.basic_weapon, self.player.spell_card):
            pool = group.pool
            active_count = pool.active_count
            if active_count <= 0:
                continue

            bullet_x = pool.x[:active_count]
            bullet_y = pool.y[:active_count]

            dx = bullet_x[:, np.newaxis] - enemy_x[np.newaxis, :]
            dy = bullet_y[:, np.newaxis] - enemy_y[np.newaxis, :]
            dist_sq = (dx * dx) + (dy * dy)
            hit_matrix = dist_sq < hit_radius_sq[np.newaxis, :]

            bullet_hit_mask = np.any(hit_matrix, axis=1)
            if np.any(bullet_hit_mask):
                pool.filter_active((~bullet_hit_mask).astype(np.bool_))

            enemy_damage += np.count_nonzero(hit_matrix, axis=0).astype(np.int32) * self._enemy_hit_damage

        if np.any(enemy_damage):
            for index, enemy in enumerate(self.enemies):
                enemy.hp -= int(enemy_damage[index])

        self._prune_dead_enemies()

    def _prune_dead_enemies(self) -> None:
        """Drop defeated enemies and spawn experience orbs."""
        if not self.enemies:
            return

        alive_mask = np.asarray([enemy.hp > 0 for enemy in self.enemies], dtype=np.bool_)
        for enemy, is_alive in zip(self.enemies, alive_mask.tolist()):
            if not is_alive:
                self._emit_enemy_death_bloom(enemy)
                self._score_kill += 40 + (max(1, enemy.drop_tier) * 20)
                self._spawn_enemy_drops(enemy)

        self.enemies = [enemy for enemy, is_alive in zip(self.enemies, alive_mask.tolist()) if is_alive]

    def _spawn_enemy_drops(self, enemy: Enemy) -> None:
        """Spawn tier-based point/exp/spell pickups for a defeated enemy."""
        tier = max(1, min(3, int(enemy.drop_tier)))

        exp_prob = (0.72, 0.84, 0.95)[tier - 1]
        point_prob = (0.68, 0.8, 0.9)[tier - 1]
        spell_prob = (0.04, 0.11, 0.2)[tier - 1]

        exp_value = (35, 45, 58)[tier - 1]
        point_value = (28, 42, 60)[tier - 1]

        if float(self._rng.random()) <= exp_prob:
            self.exp_orbs.append(ExpOrb(x=enemy.x, y=enemy.y, value=exp_value, kind="exp"))

        if float(self._rng.random()) <= point_prob:
            self.exp_orbs.append(ExpOrb(x=enemy.x, y=enemy.y, value=point_value, kind="point"))

        if float(self._rng.random()) <= spell_prob:
            self.exp_orbs.append(ExpOrb(x=enemy.x, y=enemy.y, value=1, kind="spell"))

    def _collect_pickups(self) -> None:
        """Collect nearby pickups (exp, point, spell) with vectorized checks."""
        if not self.exp_orbs:
            return

        orb_x = np.asarray([orb.x for orb in self.exp_orbs], dtype=np.float32)
        orb_y = np.asarray([orb.y for orb in self.exp_orbs], dtype=np.float32)

        dx = orb_x - np.float32(self.player.x)
        dy = orb_y - np.float32(self.player.y)
        dist_sq = (dx * dx) + (dy * dy)
        pickup_mask = dist_sq <= np.float32(self._exp_pickup_radius ** 2)

        if not np.any(pickup_mask):
            return

        gained_point = 0
        gained_spell = 0
        gained_levels = 0

        pickup_indices = np.flatnonzero(pickup_mask).tolist()
        for index in pickup_indices:
            item = self.exp_orbs[index]
            kind = str(item.kind)
            if kind == "exp":
                before_level = self.player.level
                self.player.gain_exp(int(item.value))
                gained_levels += max(0, self.player.level - before_level)
            elif kind == "point":
                gained_point += int(item.value)
            elif kind == "spell":
                gained_spell += int(max(1, item.value))

        self._score_point_pickup += gained_point
        if gained_levels > 0:
            self._score_upgrade += gained_levels * 150
        if gained_spell > 0:
            self.player.add_drop_spell_stock(gained_spell)

        keep_mask = ~pickup_mask
        self.exp_orbs = [orb for orb, keep in zip(self.exp_orbs, keep_mask.tolist()) if keep]

    def _draw_grid(self, screen: pygame.Surface) -> None:
        """Draw a camera-shifted grid as placeholder stage background."""
        grid_color = (18, 22, 32)
        start_x = -int(self.camera.x) % self._grid_step
        start_y = -int(self.camera.y) % self._grid_step

        for x_pos in range(start_x, self._screen_width, self._grid_step):
            pygame.draw.line(screen, grid_color, (x_pos, 0), (x_pos, self._screen_height), 1)
        for y_pos in range(start_y, self._screen_height, self._grid_step):
            pygame.draw.line(screen, grid_color, (0, y_pos), (self._screen_width, y_pos), 1)

    def _draw_entities(self, screen: pygame.Surface) -> None:
        """Render player icon and active enemies with camera offsets."""
        px = int(self.player.x - self.camera.x)
        py = int(self.player.y - self.camera.y)

        pygame.draw.circle(screen, self._character_profile.icon_outer_color, (px, py), int(self.player.radius))
        self._draw_heart(screen, (px, py), self._character_profile.icon_inner_color)

        if self.player.is_focus_mode:
            pygame.draw.circle(screen, (255, 255, 255), (px, py), int(self.player.hitbox_radius), width=1)
            pygame.draw.circle(screen, (255, 0, 0), (px, py), 1)

        for enemy in self.enemies:
            ex, ey = self.camera.apply(enemy.x, enemy.y)
            self._draw_enemy_marker(screen, enemy, int(ex), int(ey))

    def _draw_enemy_marker(self, screen: pygame.Surface, enemy: Enemy, x_pos: int, y_pos: int) -> None:
        """Draw enemy marker with its configured shape/color."""
        radius = int(max(4.0, enemy.radius))
        color = enemy.visual_color
        if enemy.visual_shape == "triangle":
            points = [
                (x_pos, y_pos - radius),
                (x_pos - radius, y_pos + radius),
                (x_pos + radius, y_pos + radius),
            ]
            pygame.draw.polygon(screen, color, points)
            return
        if enemy.visual_shape == "square":
            rect = pygame.Rect(0, 0, radius * 2, radius * 2)
            rect.center = (x_pos, y_pos)
            pygame.draw.rect(screen, color, rect)
            return
        if enemy.visual_shape == "hex":
            angles = np.linspace(0.0, 2.0 * np.pi, num=6, endpoint=False, dtype=np.float32)
            points = [
                (
                    x_pos + int(np.cos(angle) * radius),
                    y_pos + int(np.sin(angle) * radius),
                )
                for angle in angles.tolist()
            ]
            pygame.draw.polygon(screen, color, points)
            return

        pygame.draw.circle(screen, color, (x_pos, y_pos), radius)

    def _draw_heart(self, screen: pygame.Surface, center: tuple[int, int], color: tuple[int, int, int]) -> None:
        """Draw simple heart shape for player placeholder icon."""
        x_pos, y_pos = center
        pygame.draw.circle(screen, color, (x_pos - 3, y_pos - 2), 3)
        pygame.draw.circle(screen, color, (x_pos + 3, y_pos - 2), 3)
        pygame.draw.polygon(screen, color, [(x_pos - 7, y_pos - 1), (x_pos + 7, y_pos - 1), (x_pos, y_pos + 8)])

    def _draw_all_bullets(self, screen: pygame.Surface) -> None:
        """Batch-render active bullets."""
        self._blit_group_bullets(screen, self.player.basic_weapon, self._player_bullet_sprite)
        self._blit_group_bullets(screen, self.player.spell_card, self._player_spell_sprite)
        for enemy in self.enemies:
            self._blit_group_bullets(screen, enemy.danmaku, self._enemy_bullet_sprite)
        self._blit_group_bullets(screen, self._enemy_death_bloom, self._enemy_bullet_sprite)

    def _draw_spell_effects(self, screen: pygame.Surface) -> None:
        """Render spell visuals: Reimu orbs and Morisa laser beam."""
        for orb in self._reimu_spell_orbs:
            ox, oy = self.camera.apply(float(orb["x"]), float(orb["y"]))
            pygame.draw.circle(screen, tuple(orb["color"]), (int(ox), int(oy)), int(orb["radius"]))

        for effect in self._laser_effects:
            life = float(effect["life"])
            max_life = max(1.0e-6, float(effect["max_life"]))
            phase = 1.0 - (life / max_life)

            width_start = float(effect["width_start"])
            width_end = float(effect["width_end"])
            width = max(1, int(round(width_start + (width_end - width_start) * phase)))

            r, g, b = effect["color"]
            fade = max(0.0, 1.0 - phase)
            color = (
                int(r * fade),
                int(g * fade),
                int(b * fade),
            )

            ax, ay = self.camera.apply(float(effect["ax"]), float(effect["ay"]))
            bx, by = self.camera.apply(float(effect["bx"]), float(effect["by"]))
            pygame.draw.line(screen, color, (int(ax), int(ay)), (int(bx), int(by)), width)

    def _draw_exp_orbs(self, screen: pygame.Surface) -> None:
        """Render experience orbs as lightweight placeholders."""
        for orb in self.exp_orbs:
            ox, oy = self.camera.apply(orb.x, orb.y)
            if orb.kind == "point":
                color = (170, 170, 170)
            elif orb.kind == "spell":
                color = (110, 255, 140)
            else:
                color = (255, 235, 80)
            pygame.draw.circle(screen, color, (int(ox), int(oy)), 4)

    def _draw_hud(self, screen: pygame.Surface) -> None:
        """Render HUD with localized Chinese labels."""
        font = self._get_hud_font()
        wave_text = self._format_wave_status()
        exp_required = self.player.level * 100

        spell_text_key = "spell_cd" if self.player.available_spell_charges() <= 0 else "spell_ready"
        ready_blink = self.player.available_spell_charges() > 0 and (np.sin(self.time_value * 8.0) > 0.0)
        if self.player.available_spell_charges() <= 0:
            spell_state = f"CD {self.player.innate_spell_recover_timer:04.1f}s"
        elif self._character_profile.spell_mode == "laser_boost" and self._spell_boost_remaining > 0.0:
            spell_state = f"释放中 {self._spell_boost_remaining:04.1f}s"
        elif self._character_profile.spell_mode == "orbs" and self._reimu_spell_orbs:
            max_life = max(float(orb.get("life", 0.0)) for orb in self._reimu_spell_orbs)
            spell_state = f"释放中 {max_life:04.1f}s"
        elif self._spell_cast_flash > 0.0:
            spell_state = "释放中"
        else:
            spell_state = "OK!" if ready_blink else "OK"

        spell_value = (
            f"{spell_state} | 固有{self.player.innate_spell_stock} | 掉落{self.player.drop_spell_stock}"
        )
        invuln_text = "ON" if self._player_invuln_remaining > 0.0 else "OFF"

        lines = (
            f"{self._text('hud_wave', '波次')}: {wave_text}",
            f"{self._text('hud_lv', '等级')}: {self.player.level}",
            f"{self._text('hud_exp', '经验')}: {self.player.exp} / {exp_required}",
            f"{self._text('hud_hp', '生命')}: {self.player.current_hp} / {self.player.max_hp}",
            f"{self._text('hud_enemies', '敌人数')}: {len(self.enemies)}",
            f"{self._text('hud_orbs', '经验球')}: {len(self.exp_orbs)}",
            f"{self._text(spell_text_key, '符卡')}: {spell_value}",
            f"无敌: {invuln_text}",
        )

        y_pos = 12
        for index, text in enumerate(lines):
            color = (130, 255, 150) if index == 0 else (235, 245, 235)
            screen.blit(font.render(text, True, color), (12, y_pos))
            y_pos += 24

    def _draw_scoreboard(self, screen: pygame.Surface) -> None:
        """Render top-center translucent scoreboard with score breakdown."""
        width, _ = screen.get_size()
        panel_w = 760
        panel_h = 62
        panel_x = (width - panel_w) // 2
        panel_y = 8

        if self._score_overlay is None or self._score_overlay.get_size() != (panel_w, panel_h):
            self._score_overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            self._score_overlay.fill((10, 10, 16, 148))

        screen.blit(self._score_overlay, (panel_x, panel_y))

        font = self._get_score_font()
        remaining = self._get_next_wave_remaining()
        lines = (
            f"得分 {int(self.score)}  击杀+{self._score_kill}  生存+{int(self._score_survival)}  升级+{self._score_upgrade}",
            f"消弹+{self._score_bullet_clear}  点数+{self._score_point_pickup}  存活时间 {self.time_value:05.1f}/{remaining:04.1f}",
        )

        text_y = panel_y + 8
        for line in lines:
            text_surface = font.render(line, True, (232, 238, 245))
            screen.blit(text_surface, text_surface.get_rect(center=(width // 2, text_y + 8)))
            text_y += 24

    def _text(self, key: str, fallback: str) -> str:
        """Get localized ui text with fallback."""
        value = self._ui_texts.get(key, fallback)
        return str(value)

    def _get_hud_font(self) -> pygame.font.Font:
        """Return cached HUD font."""
        if self._hud_font is not None:
            return self._hud_font

        self._hud_font = ResourceManager.get_ui_font("hud", 24)
        return self._hud_font

    def _get_score_font(self) -> pygame.font.Font:
        """Return cached scoreboard font."""
        if self._score_font is not None:
            return self._score_font

        self._score_font = ResourceManager.get_ui_font("hud", 22)
        return self._score_font

    def _get_next_wave_remaining(self) -> float:
        """Return remaining time before next wave switch."""
        manager = self.context.get("wave_manager")
        if manager is None:
            return 0.0

        elapsed = float(getattr(manager, "_wave_elapsed", 0.0))
        duration = float(getattr(manager, "wave_duration", 30.0))
        return max(0.0, duration - elapsed)

    def _format_wave_status(self) -> str:
        """Build wave label as current wave and remaining duration."""
        manager = self.context.get("wave_manager")
        if manager is None:
            return "- / -"

        wave_index = int(getattr(manager, "current_wave_number", 1))
        elapsed = float(getattr(manager, "_wave_elapsed", 0.0))
        duration = float(getattr(manager, "wave_duration", 30.0))
        cap_method = getattr(manager, "get_spawn_cap_for_wave", None)
        if callable(cap_method):
            cap = int(cap_method(wave_index))
        else:
            cap = self._max_active_enemies
        remaining = max(0.0, duration - elapsed)
        return f"{wave_index} / {remaining:05.1f}秒 / 上限{cap}"

    def _blit_group_bullets(self, screen: pygame.Surface, group: DanmakuGroup, sprite: pygame.Surface) -> None:
        """Convert bullet pools to screen-space blit operations."""
        pool = group.pool
        active_count = pool.active_count
        if active_count <= 0:
            return

        x_vals = pool.x[:active_count] - np.float32(self.camera.x)
        y_vals = pool.y[:active_count] - np.float32(self.camera.y)

        positions = np.column_stack((x_vals, y_vals)).astype(np.int32, copy=False)
        half_w = sprite.get_width() // 2
        half_h = sprite.get_height() // 2
        positions[:, 0] -= half_w
        positions[:, 1] -= half_h

        blit_positions = list(map(tuple, positions.tolist()))
        screen.blits(list(zip(repeat(sprite, len(blit_positions)), blit_positions)), doreturn=False)
