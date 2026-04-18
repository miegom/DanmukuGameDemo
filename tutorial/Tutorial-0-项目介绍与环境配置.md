# Tutorial-0 项目介绍与环境配置

> 学习目标：理解本项目的玩法主线、代码分层和本地运行方式。

---

## 1. 游戏玩法与内容（从代码出发）

这是一个 **2D 弹幕生存** 游戏，主循环在 `main.py`：

```python
# 文件: main.py
while running:
    dt = clock.tick(60) / 1000.0
    events = pygame.event.get()

    keys = pygame.key.get_pressed()
    current_scene.process_input(events, keys)
    current_scene.update(dt)
    current_scene.draw(screen)
```

每一帧固定执行三件事：

- `process_input`：读取输入
- `update`：推进游戏状态
- `draw`：绘制当前画面

### 1.1 玩家操作

玩家输入逻辑在 `scenes/gameplay_scene.py` 的 `process_input`：

```python
self._input_x = float(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - float(
    keys[pygame.K_a] or keys[pygame.K_LEFT]
)
self._input_y = float(keys[pygame.K_s] or keys[pygame.K_DOWN]) - float(
    keys[pygame.K_w] or keys[pygame.K_UP]
)
self.player.is_focus_mode = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])

mouse_buttons = pygame.mouse.get_pressed()
self.player.is_firing = bool(mouse_buttons[0])
```

- `WASD` / 方向键：移动
- `Shift`：低速精确移动（focus）
- 鼠标左键：持续普攻
- 鼠标右键：释放符卡

### 1.2 角色与战斗风格

角色数据来源于 `assets/data/characters.json`（数据驱动）：

```json
{
  "id": "reimu",
  "display_name": "灵梦",
  "basic_mode": "danmaku",
  "spell_mode": "orbs"
}
```

```json
{
  "id": "morisa",
  "display_name": "魔理沙",
  "basic_mode": "laser",
  "spell_mode": "laser_boost"
}
```

- 灵梦：弹幕普攻 + 阴阳玉符卡
- 魔理沙：激光普攻 + 激光强化符卡

### 1.3 波次、敌人与成长

波次管理在 `logic/level_system.py`，例如刷怪上限：

```python
def get_spawn_cap_for_wave(self, wave_number: int) -> int:
    wave = max(1, int(wave_number))
    if wave <= 3:
        return 6
    if wave <= 6:
        return 9
    return 9 + (wave - 6)
```

敌人参数在 `assets/data/waves.json`（血量、AI、弹幕参数、掉落等级）。

升级系统由 `logic/roguelite_system.py` 的 `UpgradeManager` 驱动，配置在 `assets/data/upgrades.json`，通过 `character`、`requires`、`attack_channel` 实现角色分流和递进。

---

## 2. 代码架构与核心逻辑

### 2.1 目录分层

- `core/`：基础设施（日志、资源加载、对象池、相机）
- `logic/`：纯逻辑层（实体、弹幕数学、波次、升级）
- `scenes/`：场景状态机（标题、选角、战斗、升级、结算）
- `assets/`：配置与资源（JSON、字体）
- `tests/`：烟雾测试

### 2.2 入口与状态机

- 入口文件：`main.py`
- 场景基类：`scenes/base_scene.py`

```python
class BaseScene:
    def process_input(self, events, keys) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self, screen: pygame.Surface) -> None: ...
```

主循环只依赖 `BaseScene` 的统一接口，具体场景通过 `switch_to` / `switch_to_instance` 切换。

### 2.3 资源与字体

项目通过 `core/resource_mgr.py` 统一读取配置和字体，UI 字体默认来自 `assets/data/ui.json` 中的 `assets/fonts/BoutiqueBitmap7x7_Scan_Line.ttf`。

---

## 3. 性能设计

弹幕核心在 `logic/danmaku_system.py`，使用 NumPy 向量化更新：

```python
pool.x[:active] += pool.vx[:active] * np.float32(dt)
pool.y[:active] += pool.vy[:active] * np.float32(dt)
```

弹幕对象池在 `core/bullet_pool.py`，预分配数组并复用，减少频繁创建/销毁对象。

这就是项目在弹幕数量上来时仍可稳定运行的关键基础。

---

## 4. 环境配置与运行

### 4.1 依赖

`requirements.txt`：

```text
numpy>=1.24
pygame>=2.6
```

### 4.2 创建虚拟环境并安装

```bash
cd /home/miegoming/PycharmProjects/DanmukuGameDemo
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> Windows PowerShell 激活命令：`.venv\Scripts\Activate.ps1`

### 4.3 运行项目

```bash
python main.py
```

### 4.4 运行 smoke tests

```bash
python tests/danmaku_smoke.py
python tests/entity_roguelite_smoke.py
python tests/gameplay_scene_smoke.py
python tests/wave_manager_smoke.py
python tests/feature_test_scene_smoke.py
```

---

## 5. 本章小结

完成本章后，你应该能够：

1. 解释游戏每帧的核心流程。  
2. 快速定位角色、敌人、升级配置文件。  
3. 说清项目分层与入口逻辑。  
4. 在本地完成环境搭建并运行基础测试。

下一章 `Tutorial-1` 将聚焦：本项目中最常用的数据结构与流程控制写法。
