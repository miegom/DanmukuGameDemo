# DanmakuGameDemo（2D 弹幕生存游戏示例）

这是一个基于 Python + Pygame + NumPy 的 **2D 弹幕生存** 项目。
主循环在 `main.py` 中以固定帧节奏执行 `process_input`、`update`、`draw` 三个阶段。

## 玩法概览

- 移动：`WASD` / 方向键
- 精确移动（低速）：`Shift`
- 普攻：鼠标左键
- 符卡：鼠标右键

角色采用数据驱动配置（`assets/data/characters.json`）：

- 灵梦：弹幕普攻 + 阴阳玉符卡
- 魔理沙：激光普攻 + 激光强化符卡

## 项目结构

- `core/`：基础设施（日志、资源加载、对象池、相机）
- `logic/`：核心逻辑（实体、弹幕、波次、升级）
- `scenes/`：场景状态机（标题、选角、战斗、升级、结算）
- `assets/`：资源与配置（JSON、字体）
- `tests/`：烟雾测试脚本

关键模块示例：

- `core/bullet_pool.py`：弹幕对象池（预分配数组，减少频繁创建/销毁）
- `logic/danmaku_system.py`：NumPy 向量化弹幕更新与发射逻辑
- `logic/level_system.py`：波次与刷怪管理
- `logic/roguelite_system.py`：升级系统与条目筛选

## 性能设计

项目的弹幕更新使用 NumPy 向量化，配合对象池复用内存，是高弹量下保持稳定运行的基础。

## 环境配置

依赖见 `requirements.txt`：

- `numpy>=1.24`
- `pygame>=2.6`

推荐使用虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows PowerShell 激活命令：

```bash
.venv\Scripts\Activate.ps1
```

## 运行项目

```bash
python main.py
```

直接进入功能测试场景：

```bash
python main.py --feature-test
```

## 运行 Smoke Tests

```bash
python tests/danmaku_smoke.py
python tests/entity_roguelite_smoke.py
python tests/gameplay_scene_smoke.py
python tests/wave_manager_smoke.py
python tests/feature_test_scene_smoke.py
```

## 教程文档

入门建议先阅读：`tutorial/Tutorial-0-项目介绍与环境配置.md`。

