"""Resource loading and caching services with safe fallbacks."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from core.logger import logger


class ResourceManager:
    """Class-based resource manager for JSON and texture assets.

    This manager never raises exceptions for resource-loading failures.
    It logs detailed errors and returns a fallback object instead.
    """

    _texture_cache: dict[str, pygame.Surface] = {}
    _font_cache: dict[str, pygame.font.Font] = {}

    @classmethod
    def load_json(cls, path: str) -> dict[str, Any]:
        """Load a JSON file safely.

        Args:
            path: Relative or absolute JSON file path.

        Returns:
            Parsed JSON dictionary on success, otherwise an empty dictionary.
        """
        normalized_path = str(Path(path))

        try:
            with Path(normalized_path).open("r", encoding="utf-8") as file_obj:
                payload: Any = json.load(file_obj)
        except FileNotFoundError:
            logger.error("JSON file not found: %s", normalized_path)
            return {}
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse JSON '%s': %s", normalized_path, exc)
            return {}
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            logger.error("Unexpected JSON load error for '%s': %s", normalized_path, exc)
            return {}

        if not isinstance(payload, dict):
            logger.error("JSON root must be an object: %s", normalized_path)
            return {}

        logger.info("Loaded JSON: %s", normalized_path)
        return payload

    @classmethod
    def get_texture(
        cls,
        path: str,
        size: tuple[int, int] = (32, 32),
    ) -> pygame.Surface:
        """Get a texture surface from cache or disk.

        Args:
            path: Relative or absolute image path.
            size: Desired output texture size.

        Returns:
            Loaded surface on success. If loading fails, a magenta placeholder
            surface is returned.
        """
        cache_key = f"{Path(path)}::{size}"
        if cache_key in cls._texture_cache:
            return cls._texture_cache[cache_key]

        try:
            surface = pygame.image.load(path)
            if surface.get_size() != size:
                surface = pygame.transform.smoothscale(surface, size)

            cls._texture_cache[cache_key] = surface
            logger.info("Loaded texture: %s", path)
            return surface
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            logger.error("Failed to load texture '%s': %s", path, exc)
            placeholder = pygame.Surface(size)
            placeholder.fill((255, 0, 255))
            cls._texture_cache[cache_key] = placeholder
            return placeholder

    @classmethod
    def get_font(cls, path: str, size: int) -> pygame.font.Font:
        """Get a font from cache or disk with safe fallback."""
        if not pygame.font.get_init():
            pygame.font.init()

        normalized_size = max(8, int(size))
        normalized_path = str(Path(path)).strip()
        cache_key = f"{normalized_path}::{normalized_size}"
        if cache_key in cls._font_cache:
            return cls._font_cache[cache_key]

        if normalized_path:
            try:
                font = pygame.font.Font(normalized_path, normalized_size)
                cls._font_cache[cache_key] = font
                logger.info("Loaded font: %s (%d)", normalized_path, normalized_size)
                return font
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                logger.error("Failed to load font '%s': %s", normalized_path, exc)

        fallback_key = f"__default__::{normalized_size}"
        if fallback_key in cls._font_cache:
            return cls._font_cache[fallback_key]

        fallback_font = pygame.font.Font(None, normalized_size)
        cls._font_cache[fallback_key] = fallback_font
        return fallback_font

    @classmethod
    def get_ui_font(cls, role: str, default_size: int) -> pygame.font.Font:
        """Load role-based UI font from ui.json with fallback behavior."""
        payload = cls.load_json("assets/data/ui.json")
        fonts_cfg = payload.get("fonts", {}) if isinstance(payload, dict) else {}
        if not isinstance(fonts_cfg, dict):
            fonts_cfg = {}

        size_map = fonts_cfg.get("sizes", {})
        if not isinstance(size_map, dict):
            size_map = {}

        title_font = str(payload.get("title_font", "")).strip() if isinstance(payload, dict) else ""
        default_path = str(fonts_cfg.get("default_path", title_font)).strip()
        size_raw = size_map.get(role, default_size)

        try:
            size = int(size_raw)
        except (TypeError, ValueError):
            size = int(default_size)

        return cls.get_font(default_path, size)
