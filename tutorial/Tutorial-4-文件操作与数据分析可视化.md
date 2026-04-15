# Tutorial-4 文件操作与数据分析可视化

> 学习目标：掌握“读写游戏数据 -> 开启开发模式观察 -> 用数据验证功能”的完整工作流。

---

## 1. 文件操作：项目当前如何处理外部数据

### 1.1 统一入口：`ResourceManager.load_json`

当前项目对外部配置（角色、波次、UI、升级）都走统一读取入口：

```python
# 文件: core/resource_mgr.py
@classmethod
def load_json(cls, path: str) -> dict[str, Any]:
    normalized_path = str(Path(path))
    try:
        with Path(normalized_path).open("r", encoding="utf-8") as file_obj:
            payload: Any = json.load(file_obj)
    except FileNotFoundError:
        logger.error("JSON file not found: %s", normalized_path)
        return {}
    ...
```

你可以看到三个关键点：

- 路径标准化：`Path(path)`
- 数据格式转换：`json.load(...)`
- 防御式回退：读取失败返回 `{}`，避免主流程崩溃

### 1.2 这些 JSON 在哪里被使用？

- `logic/character_system.py`：读取 `assets/data/characters.json`
- `logic/level_system.py`：读取 `assets/data/waves.json`
- `logic/roguelite_system.py`：读取 `assets/data/upgrades.json`
- `scenes/title_scene.py` / `scenes/gameplay_scene.py`：读取 `assets/data/ui.json`

这就是“数据驱动”的基础：改配置优先，不先改硬编码。

---

## 2. 路径处理：`pathlib` 与 `os.path` 的关系

项目现在主要使用 `pathlib.Path`，例如：

```python
# 文件: core/resource_mgr.py
normalized_path = str(Path(path))
```

而你在 ex1（存档）任务里也可以使用 `os.path`，两种方式都可以。  
一个常见写法是把存档放到项目根目录下的 `save/` 文件夹：

```python
import os

save_dir = os.path.join(os.getcwd(), "save")
os.makedirs(save_dir, exist_ok=True)
score_path = os.path.join(save_dir, "high_score.json")
```

> 建议：项目内保持一种风格更好。当前代码风格更偏 `pathlib`。

---

## 3. 结合 ex1（存档）：JSON/TXT 存档格式怎么选

当前仓库还没有“最高分存档”的现成实现（只有 JSON 读取逻辑），所以 ex1 做存档时你会自己补写。

### 3.1 JSON 存档（推荐）

优点：结构化，可扩展（可以同时存最高分、时间、角色）。

```python
# 示例（用于 ex1）
record = {
    "high_score": 123456,
    "best_survival": 245.3,
    "character": "reimu"
}
```

### 3.2 TXT 存档（可行但信息弱）

优点：简单；缺点：后续字段扩展麻烦。

```text
high_score=123456
```

如果你计划继续做 ex2/ex3，优先 JSON。

---

## 4. DevMode 开关逻辑：如何开启开发模式

## 4.1 游戏内输入开启（已实现）

在标题场景中，输入字符串 `devmode` 会开启开发模式：

```python
# 文件: scenes/title_scene.py
self._dev_code: str = "devmode"
...
if event.unicode and event.unicode.isprintable():
    self._dev_buffer = (self._dev_buffer + event.unicode.lower())[-24:]
    if self._dev_buffer.endswith(self._dev_code):
        self.context["dev_mode"] = True
        self._dev_mode_enabled = True
```

并且提示文案来自 `assets/data/ui.json`：

```json
"title_prompt": "按回车开始（输入 devmode 开启开发模式）",
"title_devmode_hint": "开发模式已启用"
```

## 4.2 代码中强制开启（调试时常用）

你也可以在创建 `game_context` 后直接写：

```python
# 文件: main.py（调试临时改法）
game_context["dev_mode"] = True
```

这样每次启动都显示调试信息。

---

## 5. DevMode 数据可视化：屏幕上到底显示了什么

开发者信息在这里被绘制：

```python
# 文件: scenes/gameplay_scene.py
def _draw_hud(self, screen: pygame.Surface) -> None:
    self._draw_bottom_status_hud(screen)
    if self._is_dev_mode():
        self._draw_debug_hud(screen)
```

### 5.1 `_draw_debug_hud` 当前显示字段

```python
# 文件: scenes/gameplay_scene.py
lines = (
    f"波次: {wave_text}",
    f"等级: {self.player.level}",
    f"经验: {self.player.exp} / {exp_required}",
    f"生命: {self.player.current_hp} / {self.player.max_hp}",
    f"敌人数: {len(self.enemies)}",
    f"经验球: {len(self.exp_orbs)}",
    f"符卡: {spell_value}",
    f"无敌: {invuln_text}",
)
```

字段含义：

- `波次`：当前波次、下次切波剩余秒数、当前波敌人上限
- `等级/经验/生命`：玩家成长与生存状态
- `敌人数/经验球`：当前场景实体密度
- `符卡`：可用状态（`OK`/`CD`/`释放中`）+ 固有/掉落库存
- `无敌`：受击后无敌帧状态

### 5.2 关于 FPS / 内存 / 实时弹幕数量 / 碰撞线框

这几个指标在**当前版本并未接入 DevMode 文本面板**：

- FPS：未显示
- 内存占用：未显示
- 实时弹幕数量：未显示（但代码里可从各 `pool.active_count` 推导）
- 碰撞箱线框：仅在 `Shift` 聚焦时显示自机判定圈，不属于 devmode 专属

也就是说，当前 DevMode 更偏“战斗状态调试”，不是“性能分析面板”。

---

## 6. 这些数据分析手段，如何服务 ex1 / ex2

## 6.1 对 ex1（存档/升级类练习）的帮助

- 能通过 `等级/经验/符卡状态` 立即确认功能是否真正生效
- 存档功能调试时可同时对照 HUD 中 `得分` 与游戏结束场景显示值

## 6.2 对 ex2（波次/敌人节奏练习）的帮助

- 通过 `波次` 和 `敌人数` 观察改动是否符合预期
- 通过存活时间和压力变化判断“过强/过弱/过乱”

核心思路：**先读数据，再改参数，再用 DevMode 验证**。

---

## 7. 本章小结

你已经掌握了项目调试与数据工作的关键路径：

1. 通过 `ResourceManager` 统一读取配置；  
2. 理解 `devmode` 开关在场景间如何传递；  
3. 读懂调试 HUD 的每一项信息含义；  
4. 把这些信息用于 ex1/ex2 的功能验证与调参闭环。  

到这里，Tutorial-0 ~ 4 的主线学习就完整了。
