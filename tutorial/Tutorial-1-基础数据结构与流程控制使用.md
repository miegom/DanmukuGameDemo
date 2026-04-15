# Tutorial-1 基础数据结构与流程控制使用

> 学习目标：把 Python 的基础语法和项目真实代码对齐，看懂“每一帧发生了什么”。

---

## 1. 先建立整体视角：游戏每帧如何运转

先看入口 `main.py` 的核心循环：

```python
# 文件: main.py
while running:
    dt = clock.tick(60) / 1000.0
    events = pygame.event.get()

    for event in events:
        if event.type == pygame.QUIT:
            running = False
            break

    if not running:
        continue

    keys = pygame.key.get_pressed()
    current_scene.process_input(events, keys)
    current_scene.update(dt)
    current_scene.draw(screen)
    pygame.display.flip()
```

这段代码体现了最经典的 Game Loop：

- 采样时间 `dt`（用于“与帧率无关”的运动）
- 收集输入事件 `events`
- 先处理输入，再更新状态，最后渲染画面
- 每一帧刷新屏幕 `flip()`

后续你看到的所有数据结构（列表、字典、集合、元组）都在为这个循环服务。

---

## 2. Dictionary（字典）：配置与跨场景状态的“总线”

### 2.1 场景共享上下文

```python
# 文件: main.py
game_context: dict[str, Any] = {
    "score": 0,
    "weapons": {},
    "screen_width": WINDOW_WIDTH,
    "screen_height": WINDOW_HEIGHT,
}
```

`game_context` 会传给各个 Scene，作用是共享运行时状态（例如分数、窗口尺寸、角色选择等）。

### 2.2 从 JSON 读取配置（防御式）

```python
# 文件: core/resource_mgr.py
@classmethod
def load_json(cls, path: str) -> dict[str, Any]:
    ...
    try:
        with Path(normalized_path).open("r", encoding="utf-8") as file_obj:
            payload: Any = json.load(file_obj)
    except FileNotFoundError:
        logger.error("JSON file not found: %s", normalized_path)
        return {}
    ...
```

这里强制返回 `dict`（失败时返回空字典 `{}`），避免配置损坏导致游戏直接崩溃。

### 2.3 字典分层读取

```python
# 文件: scenes/gameplay_scene.py
ui_config = ResourceManager.load_json("assets/data/ui.json")
text_map = ui_config.get("texts", {}) if isinstance(ui_config, dict) else {}
self._ui_texts = text_map if isinstance(text_map, dict) else {}
```

这是一种典型写法：`外层 dict -> 内层 dict -> 最终字段`，层层校验类型。

---

## 3. List（列表）：实体容器与批量更新入口

### 3.1 列表管理游戏实体

```python
# 文件: scenes/gameplay_scene.py
self.enemies: list[Enemy] = []
self.exp_orbs: list[ExpOrb] = []
```

敌人、掉落物都是“可变数量对象”，最自然的容器就是 `list`。

### 3.2 列表追加（掉落生成）

```python
# 文件: scenes/gameplay_scene.py
if float(self._rng.random()) <= exp_prob:
    self.exp_orbs.append(ExpOrb(x=enemy.x, y=enemy.y, value=exp_value, kind="exp"))
```

### 3.3 列表安全删除（重点）

```python
# 文件: scenes/gameplay_scene.py
keep_mask = ~pickup_mask
self.exp_orbs = [orb for orb, keep in zip(self.exp_orbs, keep_mask.tolist()) if keep]
```

这比“遍历时直接 `remove`”安全很多，能避免跳项和索引错乱。

---

## 4. Set（集合）：去重与状态判重

项目中 `set` 用在“升级是否已拿过”的判重逻辑。

```python
# 文件: logic/entity.py
applied_upgrade_ids: set[str] = field(default_factory=set)
```

应用升级时写入集合：

```python
# 文件: logic/roguelite_system.py
if changed:
    if upgrade_id:
        player.applied_upgrade_ids.add(upgrade_id)
```

升级候选筛选时检查集合：

```python
# 文件: logic/roguelite_system.py
if upgrade_id and upgrade_id in player.applied_upgrade_ids:
    return False
```

`set` 的成员判断平均是 O(1)，比在 `list` 里查重更合适。

---

## 5. Tuple（元组）：固定结构的数据契约

### 5.1 固定边界

```python
# 文件: logic/entity.py
Boundaries = Tuple[float, float, float, float]
```

玩家移动使用这个固定结构：

```python
# 文件: logic/entity.py
x_min, x_max, y_min, y_max = boundaries
self.x = max(x_min, min(x_max, self.x))
self.y = max(y_min, min(y_max, self.y))
```

### 5.2 固定颜色

```python
# 文件: logic/level_system.py
def _parse_color(raw: Any, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    ...
```

`tuple[int, int, int]` 明确表达“RGB 三元组”，比裸 `list` 语义更清晰。

---

## 6. 流程控制：分支 + 循环如何驱动 Gameplay

### 6.1 输入阶段（分支）

```python
# 文件: scenes/gameplay_scene.py
for event in events:
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        self._is_paused = not self._is_paused

if self._is_paused:
    self._input_x = 0.0
    self._input_y = 0.0
    self.player.is_firing = False
    return
```

这是“状态门控”分支：暂停时直接短路后续输入处理。

### 6.2 更新阶段（循环）

```python
# 文件: scenes/gameplay_scene.py
for enemy in self.enemies:
    self._move_enemy_with_ai(enemy, dt)

for enemy in self.enemies:
    enemy.update_attack(t=frame_time, px=self.player.x, py=self.player.y)
    self._update_enemy_attack(enemy, dt=dt)
```

每帧对 `enemies` 做批处理，是最常见的游戏更新模式。

### 6.3 波次推进（while 循环）

```python
# 文件: logic/level_system.py
while self._wave_elapsed >= self._wave_duration:
    self._wave_elapsed -= self._wave_duration
    self._spawn_elapsed = 0.0
    self._wave_number += 1
    self._current_wave = self._make_wave_definition(self._wave_number)
```

该 `while` 保证“即使某帧很长，也不会漏掉波次切换”。

---

## 7. 为什么下一章必须讲“模块化”

当逻辑增长后，如果把所有内容写在一个大循环里，会出现三个问题：

- 可读性差：很难快速定位“输入/碰撞/掉落/渲染”问题
- 可测试性差：无法单独测试某个子逻辑
- 复用性差：同类功能无法在别的场景复用

项目已经在做拆分示例（`GameplayScene.update` 中调用多个子函数）：

```python
# 文件: scenes/gameplay_scene.py
self._update_group_homing_snapshots()
self._sync_basic_attack_tuning()
self.player.update_attack(t=frame_time, dt=dt)
self._resolve_player_bullet_hits()
self._attract_pickups(dt)
self._collect_pickups()
```

这就是 Tutorial-2 要讲的核心：把“大流程”拆成“职责清晰的小函数/模块”。

---

## 8. 本章小结

你现在应该能读懂：

- `dict`：共享上下文与配置读取
- `list`：实体管理与安全增删
- `set`：升级去重与快速判重
- `tuple`：固定结构的数据契约
- `if/for/while`：输入、更新、波次推进三段流程

下一章 `Tutorial-2` 我们会把这些基础语法，进一步整理成可维护的模块化代码结构。
