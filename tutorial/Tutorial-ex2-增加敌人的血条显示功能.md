# Tutorial-ex2 练习二：增加敌人的血条显示功能

> 目标：在每个敌人上方显示动态血条，血量越低，血条越短。

---

## 1. 功能目标与思路

这次练习要实现三个点：

1. 使用 `pygame.draw.rect` 绘制血条背景、前景与边框。
2. 使用 `current_hp / max_hp` 计算前景宽度比例。
3. 血条坐标跟随敌人位置，每帧更新并向上偏移。

项目分层上，这个功能应放在 `Scenes` 渲染层，不要在 `Logic` 层导入 `pygame`。

---

## 2. 先看项目中的“敌人位置更新”真实链路

### 2.1 敌人移动（逻辑层）

文件：`scenes/gameplay_scene.py`

```python
enemy.x += float(velocity[0]) * speed * dt
enemy.y += float(velocity[1]) * speed * dt
```

说明：敌人的世界坐标在 `update(dt)` 中不断变化。

### 2.2 敌人屏幕坐标（渲染层）

文件：`scenes/gameplay_scene.py`

```python
for enemy in self.enemies:
	ex, ey = self.camera.apply(enemy.x, enemy.y)
	self._draw_enemy_marker(screen, enemy, int(ex), int(ey))
```

说明：`camera.apply(...)` 把世界坐标转换成屏幕坐标。血条应复用这组坐标。

---

## 3. `pygame.draw.rect` 怎么用

常用签名：

```python
pygame.draw.rect(surface, color, rect, width=0, border_radius=0)
```

- `width=0` 表示填充矩形（常用于血条前景）。
- `width=1` 表示仅描边（常用于血条边框）。
- `rect` 可以是 `pygame.Rect(...)`，也可以是 `(x, y, w, h)`。

---

## 4. 血条比例计算公式

血量比例：

```python
ratio = max(0.0, min(1.0, current_hp / max_hp))
fill_width = int(round(full_width * ratio))
```

当 `current_hp` 下降时，`ratio` 变小，`fill_width` 变短。

---

## 5. 本项目的实际实现（已落地）

### 5.1 在 `Enemy` 中补充 `max_hp`

文件：`logic/entity.py`

```python
@dataclass(slots=True)
class Enemy:
	x: float
	y: float
	enemy_type: str = "zako_fairy_small"
	hp: int = 20
	max_hp: int = 20
	...

	def __post_init__(self) -> None:
		self.hp = max(0, int(self.hp))
		self.max_hp = max(1, int(self.max_hp), self.hp)
```

### 5.2 刷怪时同步设置 `hp` 与 `max_hp`

文件：`logic/level_system.py`

```python
hp_value = max(1, int(preset.get("hp", 20)))

return Enemy(
	x=x_pos,
	y=y_pos,
	enemy_type=enemy_type,
	hp=hp_value,
	max_hp=hp_value,
	...
)
```

### 5.3 渲染层绘制血条（核心）

文件：`scenes/gameplay_scene.py`

```python
for enemy in self.enemies:
	ex, ey = self.camera.apply(enemy.x, enemy.y)
	self._draw_enemy_marker(screen, enemy, int(ex), int(ey))
	self._draw_enemy_health_bar(screen, enemy, int(ex), int(ey))
```

血条绘制函数：

```python
def _draw_enemy_health_bar(self, screen: pygame.Surface, enemy: Enemy, x_pos: int, y_pos: int) -> None:
	max_hp = max(1, int(enemy.max_hp))
	current_hp = max(0, min(int(enemy.hp), max_hp))
	if max_hp <= 0 or current_hp <= 0:
		return

	ratio = float(np.clip(current_hp / float(max_hp), 0.0, 1.0))
	full_w = max(10, int(round(enemy.radius * self._enemy_hp_bar_width_scale)))
	bg_rect = pygame.Rect(0, 0, full_w, self._enemy_hp_bar_height)
	bg_rect.centerx = x_pos
	bg_rect.bottom = y_pos - int(enemy.radius) - self._enemy_hp_bar_offset_y

	fill_rect = pygame.Rect(bg_rect.x, bg_rect.y, max(1, int(round(full_w * ratio))), self._enemy_hp_bar_height)
	pygame.draw.rect(screen, self._enemy_hp_bar_bg_color, bg_rect, border_radius=2)
	pygame.draw.rect(screen, self._enemy_hp_bar_fg_color, fill_rect, border_radius=2)
	pygame.draw.rect(screen, self._enemy_hp_bar_border_color, bg_rect, width=1, border_radius=2)
```

> 这段实现展示了“基于敌人坐标偏移更新”的完整做法：先拿敌人屏幕坐标，再构造 `Rect` 向上偏移。

---

## 6. 数据驱动样式配置

文件：`assets/data/ui.json`

```json
"enemy_hp_bar": {
  "height": 4,
  "offset_y": 8,
  "width_scale": 2.2,
  "bg_color": [52, 20, 24],
  "fg_color": [255, 82, 92],
  "border_color": [245, 245, 245]
}
```

说明：美术样式放到 JSON 后，调 UI 不需要反复改 Python 代码。

---

## 7. 你需要关注的文件

1. `logic/entity.py`（`Enemy.max_hp`）
2. `logic/level_system.py`（刷怪赋值）
3. `scenes/gameplay_scene.py`（实际绘制血条）
4. `assets/data/ui.json`（血条样式）

> 另外，`assets/data/highscore.json` 为 ex1 的存档文件，ex2 无需修改结构，保持 `{"highscore": 数值}` 即可。

---

## 8. 验收标准

- 每个敌人头顶都有血条。
- 敌人受伤时，血条长度会按比例减少。
- 敌人移动时，血条位置始终跟随。
- 功能稳定，无崩溃和明显掉帧。

---

## 9. 自测建议

```bash
python tests/gameplay_scene_smoke.py
python main.py
```

进入战斗后观察敌人受击过程：血条应实时缩短并持续跟随敌人。

---

## 10. 进阶挑战

- 血条仅在“受击后 1.5 秒”显示，降低视觉噪声。
- 根据敌人等级给血条换色（普通/精英/BOSS）。
- 在开发者模式下额外显示 `hp / max_hp` 数字。
