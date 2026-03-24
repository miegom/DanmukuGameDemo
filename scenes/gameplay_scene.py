"""Core playable scene with decoupled logic and rendering paths."""

from __future__ import annotations

from itertools import repeat
from typing import Any

import numpy as np
import pygame

from core.camera import Camera
from core.resource_mgr import ResourceManager
from logic.danmaku_system import (
    DanmakuGroup,
    DiscreteShape,
    EmissionOperator,
    LinearMotion,
)
from logic.entity import Enemy, Player
from scenes.base_scene import BaseScene
from logic.entity import ExpOrb
from logic.level_system import WaveManager
from logic.roguelite_system import UpgradeManager


class GameplayScene(BaseScene):
    """Main gameplay scene with vectorized bullet collision detection."""

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

        self.player = Player(x=0.0, y=0.0)
        self.player.basic_weapon = DanmakuGroup(
            shape=DiscreteShape(count=5, spread=0.52, base_angle=-np.pi / 2.0),
            emission=EmissionOperator(fire_rate=11.0, speed=240.0, spin_speed=0.0),
            motions=[LinearMotion()],
            max_bullets=4096,
            bounds=(-1400.0, 1400.0, -1000.0, 1000.0),
        )
        self.player.spell_card = DanmakuGroup(
            shape=DiscreteShape(count=3, spread=0.22, base_angle=-np.pi / 2.0),
            emission=EmissionOperator(fire_rate=5.8, speed=320.0, spin_speed=0.0),
            motions=[LinearMotion()],
            max_bullets=4096,
            bounds=(-1400.0, 1400.0, -1000.0, 1000.0),
        )
        self.camera = Camera()

        self._screen_width: int = int(context.get("screen_width", 1280))
        self._screen_height: int = int(context.get("screen_height", 720))
        self._rng = np.random.default_rng(int(context.get("seed", 20260324)))
        self.enemies: list[Enemy] = []
        self.exp_orbs: list[ExpOrb] = []
        self._wave_manager: WaveManager = self.context["wave_manager"]

        self.map_bounds: tuple[float, float, float, float] = (-1200.0, 1200.0, -900.0, 900.0)
        self.enemy_speed: float = 60.0
        self.camera_smooth: float = 6.0
        self.time_value: float = 0.0
        self.frame_timer: int = 0
        self.frame_to_seconds: float = 1.0 / 60.0
        self.collision_grace_seconds: float = 0.8
        self.score: float = 0.0

        self._input_x: float = 0.0
        self._input_y: float = 0.0

        self._grid_step: int = 64
        self._bullet_radius: int = 2
        self._enemy_bullet_hit_radius_sq: float = self.player.radius ** 2
        self._player_bullet_hit_radius: float = 4.0
        self._exp_pickup_radius: float = 26.0
        self._enemy_hit_damage: int = 2
        self._max_active_enemies: int = 8

        self._player_bullet_sprite = pygame.Surface((6, 6), pygame.SRCALPHA)
        self._player_bullet_sprite.fill((80, 235, 255))
        self._player_sniper_sprite = pygame.Surface((6, 6), pygame.SRCALPHA)
        self._player_sniper_sprite.fill((255, 245, 120))
        self._enemy_bullet_sprite = pygame.Surface((6, 6), pygame.SRCALPHA)
        self._enemy_bullet_sprite.fill((255, 90, 120))
        self._hud_font: pygame.font.Font | None = None

        self.context["player"] = self.player
        self.context["gameplay_scene"] = self

    def process_input(
        self,
        events: list[pygame.event.Event],
        keys: pygame.key.ScancodeWrapper,
    ) -> None:
        """Cache movement input and handle quit shortcut."""
        del events
        self._input_x = float(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - float(
            keys[pygame.K_a] or keys[pygame.K_LEFT]
        )
        self._input_y = float(keys[pygame.K_s] or keys[pygame.K_DOWN]) - float(
            keys[pygame.K_w] or keys[pygame.K_UP]
        )

    def update(self, dt: float) -> None:
        """Run world simulation step and detect collisions."""
        if dt <= 0.0:
            return

        self.frame_timer += 1
        frame_time = float(self.frame_timer) * self.frame_to_seconds

        self.time_value += dt
        self.score += dt * 10.0
        self.context["score"] = int(self.score)

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
            max_active_enemies=self._max_active_enemies,
        )
        if spawned_enemies:
            self.enemies.extend(spawned_enemies)

        for enemy in self.enemies:
            self._move_enemy_toward_player(enemy, dt)

        if self.enemies and isinstance(self.player.spell_card.shape, DiscreteShape):
            nearest_enemy = min(
                self.enemies,
                key=lambda enemy: (enemy.x - self.player.x) ** 2 + (enemy.y - self.player.y) ** 2,
            )
            self.player.spell_card.shape.base_angle = float(
                np.arctan2(nearest_enemy.y - self.player.y, nearest_enemy.x - self.player.x)
            )

        self.player.update_attack(t=frame_time)
        for enemy in self.enemies:
            if isinstance(enemy.danmaku.shape, DiscreteShape):
                enemy.danmaku.shape.base_angle = float(
                    np.arctan2(self.player.y - enemy.y, self.player.x - enemy.x)
                )
            enemy.update_attack(t=frame_time, px=self.player.x, py=self.player.y)

        self._resolve_player_bullet_hits()
        self._collect_exp_orbs()

        if self.player.level_up:
            from scenes.upgrade_scene import UpgradeScene

            self.context["player_state"] = {
                "x": self.player.x,
                "y": self.player.y,
                "level": self.player.level,
                "exp": self.player.exp,
                "max_hp": self.player.max_hp,
                "current_hp": self.player.current_hp,
            }
            self.context["player"] = self.player
            self.context["gameplay_scene"] = self
            self.context["previous_gameplay_scene"] = self
            self.player.level_up = False
            self.switch_to(UpgradeScene)
            return

        if self.time_value >= self.collision_grace_seconds and self._check_enemy_bullet_collision():
            from scenes.gameover_scene import GameOverScene

            self.switch_to(GameOverScene)

    def draw(self, screen: pygame.Surface) -> None:
        """Render map grid, entities, and batched bullet sprites."""
        self._screen_width, self._screen_height = screen.get_size()
        screen.fill((8, 10, 16))

        self._draw_grid(screen)
        self._draw_entities(screen)
        self._draw_all_bullets(screen)
        self._draw_exp_orbs(screen)
        self._draw_hud(screen)

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

    def _create_test_enemies(self, count: int) -> list[Enemy]:
        """Legacy debug helper retained for compatibility (unused in normal run)."""
        del count
        return []

    def _move_enemy_toward_player(self, enemy: Enemy, dt: float) -> None:
        """Move a single enemy toward player position."""
        delta = np.asarray([self.player.x - enemy.x, self.player.y - enemy.y], dtype=np.float32)
        distance = float(np.linalg.norm(delta))
        if distance <= 1.0e-6:
            return

        velocity = delta / np.float32(distance)
        enemy.x += float(velocity[0]) * self.enemy_speed * dt
        enemy.y += float(velocity[1]) * self.enemy_speed * dt

    def _check_enemy_bullet_collision(self) -> bool:
        """Vectorized collision test between player and all enemy bullets."""
        enemy_x_arrays = [enemy.danmaku.pool.x[:enemy.danmaku.pool.active_count] for enemy in self.enemies]
        enemy_y_arrays = [enemy.danmaku.pool.y[:enemy.danmaku.pool.active_count] for enemy in self.enemies]

        if not enemy_x_arrays:
            return False

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

    def _resolve_player_bullet_hits(self) -> None:
        """Apply vectorized player-bullet hits to enemies and drop experience."""
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
                pool.filter_active(~bullet_hit_mask)

            enemy_damage += np.count_nonzero(hit_matrix, axis=0).astype(np.int32) * self._enemy_hit_damage

        if not np.any(enemy_damage):
            return

        for index, enemy in enumerate(self.enemies):
            enemy.hp -= int(enemy_damage[index])

        alive_mask = np.asarray([enemy.hp > 0 for enemy in self.enemies], dtype=np.bool_)
        for enemy, is_alive in zip(self.enemies, alive_mask.tolist()):
            if not is_alive:
                self.exp_orbs.append(ExpOrb(x=enemy.x, y=enemy.y, value=40))

        # Rebuild enemy list in one pass to avoid mutation during iteration.
        self.enemies = [enemy for enemy, is_alive in zip(self.enemies, alive_mask.tolist()) if is_alive]

    def _collect_exp_orbs(self) -> None:
        """Collect nearby experience orbs with vectorized distance checks."""
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

        values = np.asarray([orb.value for orb in self.exp_orbs], dtype=np.int32)
        total_exp = int(np.sum(values[pickup_mask]))
        self.player.gain_exp(total_exp)

        keep_mask = ~pickup_mask
        # Rebuild orb list with only uncollected entries.
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
        """Render player and enemies using primitive placeholders."""
        px, py = self.camera.apply(self.player.x, self.player.y)
        pygame.draw.circle(
            screen,
            (150, 210, 255),
            (int(px), int(py)),
            int(self.player.radius),
        )

        for enemy in self.enemies:
            ex, ey = self.camera.apply(enemy.x, enemy.y)
            rect = pygame.Rect(0, 0, int(enemy.radius * 2), int(enemy.radius * 2))
            rect.center = (int(ex), int(ey))
            pygame.draw.rect(screen, (255, 120, 140), rect)

    def _draw_all_bullets(self, screen: pygame.Surface) -> None:
        """Batch-render all active bullets via ``screen.blits``."""
        self._blit_group_bullets(screen, self.player.basic_weapon, self._player_bullet_sprite)
        self._blit_group_bullets(screen, self.player.spell_card, self._player_sniper_sprite)

        for enemy in self.enemies:
            self._blit_group_bullets(screen, enemy.danmaku, self._enemy_bullet_sprite)

    def _draw_exp_orbs(self, screen: pygame.Surface) -> None:
        """Render experience orbs as lightweight placeholders."""
        for orb in self.exp_orbs:
            ox, oy = self.camera.apply(orb.x, orb.y)
            pygame.draw.circle(screen, (255, 235, 80), (int(ox), int(oy)), 4)

    def _draw_hud(self, screen: pygame.Surface) -> None:
        """Render a compact text HUD for runtime debugging metrics."""
        font = self._get_hud_font()
        wave_text = self._format_wave_status()
        exp_required = self.player.level * 100

        lines = (
            f"Wave: {wave_text}",
            f"Player LV: {self.player.level}",
            f"EXP: {self.player.exp} / {exp_required}",
            f"HP: {self.player.current_hp} / {self.player.max_hp}",
            f"Enemies: {len(self.enemies)}",
            f"Exp Orbs: {len(self.exp_orbs)}",
        )

        y_pos = 12
        for index, text in enumerate(lines):
            color = (130, 255, 150) if index == 0 else (235, 245, 235)
            screen.blit(font.render(text, True, color), (12, y_pos))
            y_pos += 24

    def _get_hud_font(self) -> pygame.font.Font:
        """Return cached HUD font with SysFont fallback."""
        if self._hud_font is not None:
            return self._hud_font

        if not pygame.font.get_init():
            pygame.font.init()

        try:
            self._hud_font = pygame.font.Font(None, 24)
        except Exception:
            self._hud_font = pygame.font.SysFont(None, 24)
        return self._hud_font

    def _format_wave_status(self) -> str:
        """Build wave label as 'current / remaining_seconds'."""
        manager = self.context.get("wave_manager")
        if manager is None:
            return "- / -"

        wave_index = int(getattr(manager, "current_wave_index", 0)) + 1
        waves = getattr(manager, "waves", [])
        elapsed = float(getattr(manager, "_wave_elapsed", 0.0))

        if isinstance(waves, list) and 0 <= (wave_index - 1) < len(waves):
            duration = float(getattr(waves[wave_index - 1], "duration", 0.0))
            if duration > 1.0e9:
                return f"{wave_index} / INF"
            remaining = max(0.0, duration - elapsed)
            return f"{wave_index} / {remaining:05.1f}s"

        return f"{wave_index} / -"

    def _blit_group_bullets(
        self,
        screen: pygame.Surface,
        group: DanmakuGroup,
        sprite: pygame.Surface,
    ) -> None:
        """Convert bullet pool arrays to screen-space blit operations."""
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

