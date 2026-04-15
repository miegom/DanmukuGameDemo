# Tutorial-ex3 练习三：添加一个开发者调试显示项

> 目标：在不破坏分层的前提下，给 `dev_mode` HUD 增加一个有用指标。

## 任务描述

在开发者模式下（标题输入 `devmode`）额外显示：

- 当前玩家子弹数量（普攻池 active_count）
- 当前敌方总子弹数量（含死亡开花池）

并在战斗中实时刷新。

---

## 你需要修改的文件

1. `scenes/gameplay_scene.py`（推荐仅改 `_draw_debug_hud` 附近）

---

## 参考原理（真实代码）

开发者模式入口（标题场景）：

```python
# 文件: scenes/title_scene.py
if self._dev_buffer.endswith(self._dev_code):
    self.context["dev_mode"] = True
```

开发者 HUD 条件渲染：

```python
# 文件: scenes/gameplay_scene.py
if self._is_dev_mode():
    self._draw_debug_hud(screen)
```

子弹池活跃数量可直接读：

```python
# 普攻
self.player.basic_weapon.pool.active_count

# 敌方开花池
self._enemy_death_bloom.pool.active_count
```

---

## 实现提示

你可以在 `_draw_debug_hud` 里加两行：

- `玩家弹数: ...`
- `敌弹总数: ...`

敌弹总数需要累加 `self.enemies` 中每个 `enemy.danmaku.pool.active_count`，再加 `self._enemy_death_bloom.pool.active_count`。

---

## 验收标准

- 非开发者模式下不显示新增信息
- 开启开发者模式后可实时看到两个计数
- 快速刷怪时计数变化明显且不会报错

---

## 自测建议

```bash
python main.py --feature-test
```

进入标题后输入 `devmode`，开始游戏观察左上角详细信息是否包含新增行。

---

## 进阶挑战

给该调试数据增加颜色阈值：

- 弹数 < 200：绿色
- 200~500：黄色
- > 500：红色

用于快速判断性能压力。
