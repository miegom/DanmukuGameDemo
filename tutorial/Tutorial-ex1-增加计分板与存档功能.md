# Tutorial-ex1 练习一：增加计分板与本地最高分存档

> 目标：实现「战斗中实时显示得分」+「游戏结束后保存最高分到本地文件」。

---

## 1. 本练习要做什么

你将完成三件事：

1. 在战斗逻辑中维护分数（击杀、生存、升级、消弹、拾取点数）。
2. 在 `Pygame` 渲染阶段把分数实时画到屏幕上。
3. 在 `GameOver` 时把最高分写入本地文件，并在下次读取。

这个练习非常接近真实开发流程：**先有数据，再有显示，最后做持久化**。

---

## 2. 先看项目里已经存在的“分数链路”（真实代码）

### 2.1 分数变量定义（数据层）

文件：`scenes/gameplay_scene.py`

```python
self.score: float = 0.0
self._score_kill: int = 0
self._score_survival: float = 0.0
self._score_upgrade: int = 0
self._score_bullet_clear: int = 0
self._score_point_pickup: int = 0
```

这段代码把总分拆成多个来源，后续调平衡会很方便。

### 2.2 在 `update(dt)` 中汇总总分

文件：`scenes/gameplay_scene.py`

```python
self._score_survival += dt * 10.0
self.score = (
    float(self._score_kill)
    + self._score_survival
    + float(self._score_upgrade)
    + float(self._score_bullet_clear)
    + float(self._score_point_pickup)
)
self.context["score"] = int(self.score)
```

重点：`self.context["score"]` 把分数放入场景共享上下文，`GameOverScene` 可以直接读。

### 2.3 敌人死亡时加分

文件：`scenes/gameplay_scene.py`

```python
if not is_alive:
    self._emit_enemy_death_bloom(enemy)
    self._score_kill += 40 + (max(1, enemy.drop_tier) * 20)
    self._spawn_enemy_drops(enemy)
```

这里就是“敌人销毁 -> 击杀得分增加”的核心位置。

---

## 3. 在主循环中显示 UI（计分板渲染）

### 3.1 渲染调用入口

文件：`main.py`

```python
current_scene.process_input(events, keys)
current_scene.update(dt)
current_scene.draw(screen)
```

每一帧都先更新数据，再绘制屏幕。计分板属于 `draw(screen)` 阶段。

### 3.2 项目中现有的计分板实现

文件：`scenes/gameplay_scene.py`

```python
lines = (
    f"得分 {int(self.score)}  击杀+{self._score_kill}  生存+{int(self._score_survival)}  升级+{self._score_upgrade}",
    f"消弹+{self._score_bullet_clear}  点数+{self._score_point_pickup}  存活时间 {self.time_value:05.1f}/{remaining:04.1f}",
)

for line in lines:
    text_surface = font.render(line, True, (232, 238, 245))
    screen.blit(text_surface, text_surface.get_rect(center=(width // 2, text_y + 8)))
```

这段就是标准 `pygame.font.Font.render(...) + blit(...)` 文本 UI 绘制方式。

---

## 4. 游戏结束时显示结算分数

文件：`scenes/gameover_scene.py`

```python
self._score_value = int(self.context.get("score", 0))
score_surface = self._info_font.render(
    f"得分: {self._score_value}",
    True,
    (240, 230, 230),
)
```

因为 `GameplayScene` 写入了 `context["score"]`，这里无需重复计算。

---

## 5. 最高分存档（已落地实现）

本项目现在已经实装为：`assets/data/highscore.json` 持久化最高分。

### 5.1 存档模块

文件：`core/save_system.py`

```python
from __future__ import annotations

import json
from pathlib import Path


HIGHSCORE_PATH = Path("assets/data/highscore.json")


def load_highscore() -> int:
    """Load highscore from assets JSON file with safe fallback."""
    payload = ResourceManager.load_json(str(HIGHSCORE_PATH))
    if not isinstance(payload, dict):
        return 0
    return _parse_highscore(payload)


def save_highscore_if_needed(score: int) -> int:
    """Persist highscore when current score beats recorded score."""
    current_score = max(0, int(score))
    previous_high = load_highscore()
    new_high = max(previous_high, current_score)
    if new_high <= previous_high:
        return previous_high

    HIGHSCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HIGHSCORE_PATH.open("w", encoding="utf-8") as file_obj:
        json.dump({"highscore": new_high}, file_obj, ensure_ascii=False, indent=2)
    return new_high
```

说明：

- 读取使用 `ResourceManager.load_json(...)`，符合项目“统一资源加载 + fallback”规范。
- 写入使用 `Path.open(..., "w") + json.dump(...)`，并在模块里记录日志与异常保护。

### 5.2 结算场景接入存档

文件：`scenes/gameover_scene.py`

```python
from core.save_system import save_highscore_if_needed

self._score_value: int = int(self.context.get("score", 0))
self._highscore_value: int = save_highscore_if_needed(self._score_value)
```

并在 `draw()` 中渲染：

```python
score_surface = self._info_font.render(
    f"得分: {self._score_value}",
    True,
    (240, 230, 230),
)
highscore_surface = self._info_font.render(
    f"最高分: {self._highscore_value}",
    True,
    (210, 235, 210),
)
```

---

## 6. 你将修改哪些文件（建议）

1. `scenes/gameplay_scene.py`（实时计分 + 计分板渲染）
2. `scenes/gameover_scene.py`（结算页写入并显示最高分）
3. `core/save_system.py`（新增：高分读取与持久化）
4. `assets/data/highscore.json`（高分存档文件）
5. `assets/data/ui.json`（新增 `gameover_highscore` 文本键）

---

## 7. 验收标准

- 战斗中顶部计分板实时变化。
- 结束界面显示本局得分。
- `assets/data/highscore.json` 存在且结构正确（`{"highscore": 数值}`）。
- 新分数高于旧记录时，`highscore` 正确更新；否则保持不变。

---

## 8. 自测步骤

```bash
python main.py
```

进入战斗后击杀敌人观察分数变化，结束游戏后检查：`assets/data/highscore.json`。

---

## 9. 进阶练习

- 把“本局得分构成明细”也写入存档（例如 `kill_score`、`survival_score`）。
- 在 `TitleScene` 增加“历史最高分”展示。
- 将存档写入封装接入 `Logger`，统一错误日志风格。
