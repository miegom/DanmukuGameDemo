# Tutorial-2 模块化函数应用

> 学习目标：按项目真实文件顺序，看懂“谁负责什么”，以及模块之间如何协作。

---

## 1. 为什么需要模块化？

在弹幕游戏里，每一帧都要处理输入、移动、碰撞、生成敌人、渲染 UI。  
如果把这些都写在一个文件里，代码会很快变得难改、难测、难扩展。

本项目采用的是分层模块化：

- `core/`：底层能力（日志、资源、对象池、相机）
- `logic/`：纯业务逻辑（实体、弹幕、波次、升级）
- `scenes/`：状态机与场景编排（标题、选角、战斗、升级、结算）
- `tests/`：烟雾测试（确保关键路径可运行）

---

## 2. 项目结构树（按实际文件夹与 .py 顺序）

```text
DanmukuGameDemo/
├── main.py
├── core/
│   ├── bullet_pool.py
│   ├── camera.py
│   ├── io_system.py
│   ├── logger.py
│   ├── renderer.py
│   └── resource_mgr.py
├── logic/
│   ├── character_system.py
│   ├── danmaku_system.py
│   ├── entity.py
│   ├── level_system.py
│   └── roguelite_system.py
├── scenes/
│   ├── base_scene.py
│   ├── feature_test_scene.py
│   ├── gameover_scene.py
│   ├── gameplay_scene.py
│   ├── select_scene.py
│   ├── title_scene.py
│   └── upgrade_scene.py
└── tests/
    ├── danmaku_smoke.py
    ├── entity_roguelite_smoke.py
    ├── feature_test_scene_smoke.py
    ├── gameplay_scene_smoke.py
    └── wave_manager_smoke.py
```

---

## 3. 核心 `.py` 文件职责总览

> 下面按“目录顺序 + 文件顺序”快速梳理。

### 3.1 入口

- `main.py`：程序入口与总循环，统一调用 `scene.process_input -> scene.update -> scene.draw`，并处理场景切换。

### 3.2 `core/`（底层基础设施）

- `core/bullet_pool.py`：`NumpyBulletPool` 对象池，预分配数组并支持 `spawn_batch/filter_active`。
- `core/camera.py`：2D 相机坐标换算（世界坐标转屏幕坐标）。
- `core/io_system.py`：输入层占位（当前实现较轻，可作为后续扩展点）。
- `core/logger.py`：统一日志格式与输出。
- `core/renderer.py`：渲染管线占位（当前渲染主要在 Scene 中完成）。
- `core/resource_mgr.py`：统一资源入口（`load_json`、`get_font`、`get_ui_font`），并带 fallback。

### 3.3 `logic/`（纯逻辑）

- `logic/character_system.py`：角色配置解析，输出 `CharacterProfile`。
- `logic/danmaku_system.py`：弹幕核心系统，包含形状、发射器、运动算子、`DanmakuGroup`。
- `logic/entity.py`：实体模型（`Player`/`Enemy`/`ExpOrb`）与玩家成长、攻击等行为。
- `logic/level_system.py`：波次和刷怪管理（`WaveManager`）。
- `logic/roguelite_system.py`：升级池读取、筛选、应用（`UpgradeManager`）。

### 3.4 `scenes/`（状态机与画面组织）

- `scenes/base_scene.py`：统一场景接口与切换协议。
- `scenes/feature_test_scene.py`：功能压测场景（继承战斗场景，注入测试逻辑）。
- `scenes/gameover_scene.py`：结算场景（显示分数并返回标题）。
- `scenes/gameplay_scene.py`：主战斗场景（输入处理、状态推进、碰撞、渲染 HUD）。
- `scenes/select_scene.py`：选角场景（角色切换与确认）。
- `scenes/title_scene.py`：标题场景（开始输入、开发者模式入口）。
- `scenes/upgrade_scene.py`：升级场景（三选一并返回战斗）。

### 3.5 `tests/`（可运行验证）

- `tests/*.py`：对弹幕、波次、场景主路径做 smoke test，防止重构后主流程失效。

---

## 4. 跨文件调用案例 A：场景切换链路（Title -> Main -> Select）

### 4.1 调用片段

```python
# 文件: scenes/title_scene.py
if event.key in (pygame.K_RETURN, pygame.K_SPACE):
    from scenes.select_scene import SelectScene
    self.switch_to(SelectScene)
```

```python
# 文件: scenes/base_scene.py
def switch_to(self, scene_class: type[BaseScene]) -> None:
    self.next_scene_instance = None
    self.next_scene_class = scene_class
```

```python
# 文件: main.py
next_scene_class = _get_next_scene_class(current_scene)
if next_scene_class is not None:
    current_scene = next_scene_class(game_context)
```

### 4.2 为什么这就是好的模块化？

- `TitleScene` 只负责“提出切换请求”，不直接管理主循环。
- `BaseScene` 统一切换协议，所有场景都可复用。
- `main.py` 作为调度中心，统一执行“何时真正切换”。

结果是：新增场景时，只要遵守 `BaseScene` 接口，几乎不用动主循环。

---

## 5. 跨文件调用案例 B：升级应用链路（UpgradeScene -> UpgradeManager -> Player）

### 5.1 调用片段

```python
# 文件: scenes/upgrade_scene.py
upgrade = self._choices[index]
self._upgrade_manager.apply_upgrade(upgrade, player)
```

```python
# 文件: logic/roguelite_system.py
if upgrade_type == "player_tuning":
    changed = self._apply_player_tuning_upgrade(upgrade_dict, player)
```

```python
# 文件: logic/entity.py
def apply_tuning(self, param: str, mode: str, value: float) -> bool:
    if not hasattr(self.tuning, param):
        return False
    ...
    setattr(self.tuning, param, float(updated))
    return True
```

### 5.2 为什么这条链路设计合理？

- `UpgradeScene` 只负责 UI 与玩家选择。
- `UpgradeManager` 负责升级规则与校验（是否可用、是否已拿过、前置条件）。
- `Player` 负责实际数据变更（最终写入角色属性）。

这让“展示层”“规则层”“数据层”职责分离，后续加新升级类型时改动更可控。

---

## 6. 从本章到下一步

你现在可以把项目看成一套清晰的流水线：

1. `main.py` 驱动帧循环与场景调度。  
2. `scenes/` 负责流程编排与表现。  
3. `logic/` 负责可复用、可测试的业务规则。  
4. `core/` 提供全局基础能力。  

这就是“模块化函数应用”的核心价值：**高内聚、低耦合、便于扩展与测试**。
