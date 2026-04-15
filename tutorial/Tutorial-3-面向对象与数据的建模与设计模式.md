# Tutorial-3 面向对象与数据的建模与设计模式

> 学习目标：深入理解本项目“弹幕组（DanmakuGroup）”的对象建模、设计模式与系统协作方式。

---

## 1. 为什么弹幕组是本项目的建模核心？

在本项目里，玩家普攻、玩家符卡、敌人弹幕，本质上都统一为同一种对象：`DanmakuGroup`。  
这意味着你只要理解一个核心类，就能看懂大部分战斗系统。

一句话概括：**DanmakuGroup = 发射规则（Shape + Emission）+ 运动规则（Motions）+ 存储容器（Pool）**。

---

## 2. 面向对象建模：核心类与初始化方式

### 2.1 核心类定义（组合式对象）

```python
# 文件: logic/danmaku_system.py
@dataclass(slots=True)
class DanmakuGroup:
    shape: BaseShape
    emission: EmissionOperator
    motions: list[MotionOperator] = field(default_factory=list)
    max_bullets: int = 8192
    bounds: tuple[float, float, float, float] = (-256.0, 256.0, -256.0, 256.0)
    max_lifetime: float = 3.2

    __pool: NumpyBulletPool = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.__pool = NumpyBulletPool(max_size=self.max_bullets)
```

这里体现了典型“组合优于继承”：

- 不把所有行为硬写死在一个巨型类里
- 而是把形状、发射、运动拆成可替换部件
- 最后组合成一个完整弹幕对象

### 2.2 玩家侧初始化（同一抽象，不同参数）

```python
# 文件: scenes/gameplay_scene.py
self.player.basic_weapon = DanmakuGroup(
    shape=DiscreteShape(count=profile.basic_bullet_count, spread=profile.basic_bullet_spread, base_angle=-np.pi / 2.0),
    emission=EmissionOperator(fire_rate=profile.basic_fire_rate, speed=profile.basic_bullet_speed, spin_speed=0.0),
    motions=[LinearMotion()],
    max_bullets=4096,
    bounds=(-2800.0, 2800.0, -2200.0, 2200.0),
    max_lifetime=max(0.2, float(profile.basic_bullet_lifetime)),
)
```

同一个类 `DanmakuGroup`，只换参数就能变成不同角色、不同武器风格。

### 2.3 敌人侧初始化（统一模型复用）

```python
# 文件: logic/level_system.py
danmaku = DanmakuGroup(
    shape=DiscreteShape(count=max(1, int(preset.get("burst_fan_count", 3))), spread=float(preset.get("burst_spread", 0.2)), base_angle=0.0),
    emission=EmissionOperator(fire_rate=0.0, speed=float(preset.get("burst_bullet_speed", 150.0)), spin_speed=0.0),
    motions=[LinearMotion()],
    max_bullets=2048,
    bounds=(-4000.0, 4000.0, -3200.0, 3200.0),
    max_lifetime=max(0.2, float(preset.get("bullet_max_lifetime", 2.8))),
)
```

玩家与敌人都使用同一抽象，减少了系统复杂度和重复实现。

---

## 3. 这里用了哪些面向对象特性？

### 3.1 封装（Encapsulation）

`DanmakuGroup` 的弹幕数据池是私有字段 `__pool`，外部只通过 `pool` 属性读写：

```python
# 文件: logic/danmaku_system.py
@property
def pool(self) -> NumpyBulletPool:
    return self.__pool
```

好处：内部实现（数组结构、过滤方式）可以重构，不影响外部调用者。

### 3.2 继承（Inheritance）

弹幕形状和运动都使用抽象基类继承体系：

```python
# 文件: logic/danmaku_system.py
class BaseShape(ABC):
    @abstractmethod
    def angles(self, t: float) -> np.ndarray:
        ...

class MotionOperator(ABC):
    @abstractmethod
    def apply(self, pool: NumpyBulletPool, dt: float) -> None:
        ...
```

具体子类：`RingShape`、`DiscreteShape`、`LinearMotion`、`SwirlMotion`、`OrbitMotion`、`HomingMotion`。

### 3.3 多态（Polymorphism）

`DanmakuGroup` 不关心 motion 的具体类型，只调用统一接口：

```python
# 文件: logic/danmaku_system.py
for operator in self.motions:
    operator.apply(self.__pool, dt)
```

这就是运行时多态：同一调用点，执行不同算法。

---

## 4. 设计模式分析（结合真实代码）

## 4.1 对象池模式（Object Pool）——已明确采用

### 证据代码

```python
# 文件: core/bullet_pool.py
self.x: np.ndarray = np.empty(max_size, dtype=np.float32)
self.y: np.ndarray = np.empty(max_size, dtype=np.float32)
self.vx: np.ndarray = np.empty(max_size, dtype=np.float32)
self.vy: np.ndarray = np.empty(max_size, dtype=np.float32)
self.life: np.ndarray = np.empty(max_size, dtype=np.float32)
```

```python
# 文件: core/bullet_pool.py
def filter_active(self, valid_mask: np.ndarray) -> int:
    survivor_count = int(np.count_nonzero(valid_mask))
    ...
    self.active_count = survivor_count
```

### 解析

- 启动时预分配内存，避免每帧频繁创建/销毁子弹对象
- 活跃子弹始终压缩在 `[0, active_count)`，便于向量化更新
- 对弹幕游戏这种“高频生成/高频销毁”场景非常关键

## 4.2 策略模式（Strategy）——核心模式

运动算子通过 `MotionOperator.apply()` 注入到 `motions` 列表：

```python
# 文件: logic/danmaku_system.py
motions: list[MotionOperator] = field(default_factory=list)
```

升级系统还能运行时增加新策略：

```python
# 文件: logic/roguelite_system.py
if motion_name == "swirl":
    return SwirlMotion(angular_speed=angular_speed)
if motion_name == "orbit":
    return OrbitMotion(angular_speed=angular_speed)
if motion_name == "homing":
    return HomingMotion(...)
```

这让“新增一种弹道行为”变成新增一个类，而不是修改大量旧逻辑。

## 4.3 工厂模式（Factory）——轻量实现

`WaveManager._build_enemy()`根据 `enemy_type + preset` 统一构建 `Enemy`（含 `DanmakuGroup`）：

```python
# 文件: logic/level_system.py
def _build_enemy(self, enemy_type: str, x_pos: float, y_pos: float) -> Enemy:
    preset = self._enemy_presets.get(enemy_type)
    ...
    return Enemy(..., danmaku=danmaku, ...)
```

这是典型“按配置生产对象”的工厂化思想。

## 4.4 状态模式（State）——局部状态机思想

敌人攻击流程使用状态字段 + 状态转移：

```python
# 文件: scenes/gameplay_scene.py
enemy.attack_state_timer -= dt
if enemy.attack_waves_left <= 0:
    ...
self._emit_enemy_fan(enemy)
enemy.attack_waves_left -= 1
enemy.attack_state_timer = enemy.burst_cooldown if enemy.attack_waves_left <= 0 else enemy.burst_interval
```

虽然没有独立 `State` 类，但行为上属于“状态机驱动”。

---

## 5. 系统交互：弹幕对象如何融入整场战斗

下面按“输入 -> 更新 -> 碰撞 -> 渲染”看弹幕链路。

### 5.1 与 Player 的交互：玩家驱动弹幕更新

```python
# 文件: logic/entity.py
def update_attack(self, t: float, dt: float = 1.0 / 60.0) -> None:
    ...
    self._update_group_with_optional_emission(self.basic_weapon, t=t, can_emit=self.is_firing)
    ...
    self._update_group_with_optional_emission(self.spell_card, t=t, can_emit=False)
```

`Player` 不直接操作底层数组，而是调用武器组的统一更新接口。

### 5.2 与 GameplayScene 的交互：每帧统一调度

```python
# 文件: scenes/gameplay_scene.py
self.player.update_attack(t=frame_time, dt=dt)
for enemy in self.enemies:
    enemy.update_attack(t=frame_time, px=self.player.x, py=self.player.y)
    self._update_enemy_attack(enemy, dt=dt)
```

`GameplayScene` 负责时序编排，`Player/Enemy` 负责各自弹幕通道。

### 5.3 与碰撞系统的交互：直接读取池数组做向量化判定

```python
# 文件: scenes/gameplay_scene.py
pool = group.pool
active_count = pool.active_count
bullet_x = pool.x[:active_count]
bullet_y = pool.y[:active_count]
...
bullet_hit_mask = np.any(hit_matrix, axis=1)
if np.any(bullet_hit_mask):
    pool.filter_active((~bullet_hit_mask).astype(np.bool_))
```

碰撞直接基于 `NumpyBulletPool` 的连续数组进行批处理，性能高且结构清晰。

### 5.4 与渲染系统的交互：从池到屏幕批量绘制

```python
# 文件: scenes/gameplay_scene.py
x_vals = pool.x[:active_count] - np.float32(self.camera.x)
y_vals = pool.y[:active_count] - np.float32(self.camera.y)
...
screen.blits(list(zip(repeat(sprite, len(blit_positions)), blit_positions)), doreturn=False)
```

这里体现“逻辑数据 -> 渲染坐标”的标准解耦路径：

- 逻辑层只维护世界坐标
- Scene 在绘制阶段做相机换算
- 最终批量 blit 降低绘制开销

---

## 6. 进阶读者可关注的设计收益

- **一致性**：玩家/敌人弹幕同构，降低理解成本
- **可扩展**：新增弹道只需新增 `MotionOperator` 子类
- **可维护**：对象池与碰撞/渲染通过清晰接口连接
- **性能友好**：池化 + NumPy 向量化 + 批量绘制形成闭环

---

## 7. 本章小结

围绕 `DanmakuGroup`，你已经看到一个完整的工程化建模范式：

1. 用 OOP 把“发射、运动、存储”分层封装；  
2. 用对象池、策略、工厂、状态机思想组织复杂行为；  
3. 通过 `Player`、`GameplayScene`、碰撞与渲染系统完成端到端协作。  

下一章 `Tutorial-4` 将转到“文件操作与数据分析可视化”：我们会把这些运行时数据反向用于调参与平衡。
