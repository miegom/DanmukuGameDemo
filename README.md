# Touhou Survivors Core Scaffold

This repository contains a minimal Python game architecture scaffold with a
vectorized data-oriented danmaku core.

## Components

- `core/logger.py`: stdout logger with unified format.
- `core/resource_mgr.py`: resilient JSON/texture loading with fallbacks.
- `core/bullet_pool.py`: preallocated NumPy bullet storage.
- `logic/danmaku_system.py`: composable emission and motion operators.

## Quick Start

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run smoke test:

```powershell
python tests/danmaku_smoke.py
```

Run entity + roguelite smoke test:

```powershell
python tests/entity_roguelite_smoke.py
```

Run gameplay scene smoke test:

```powershell
python tests/gameplay_scene_smoke.py
```

Run wave manager smoke test:

```powershell
python tests/wave_manager_smoke.py
```

Run feature-test scene smoke test:

```powershell
python tests/feature_test_scene_smoke.py
```

Boot directly into feature-test scene:

```powershell
python main.py --feature-test
```

