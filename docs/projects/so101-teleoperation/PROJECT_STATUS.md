# SO101 Teleoperation 项目状态

> 快照日期：2026-10-30（Asia/Shanghai）  
> 用途：为后续 agent 提供可审计的项目总览。本文整合历史会话、项目文件和既有交接记录；没有把历史端口、历史相机编号或软件测试结果当作当前硬件事实。

> 2026-11-03 更新：本文主体保留 10 月 30 日的基础链路快照。其后已完成单相机自训练 ACT、P=32、自动粗归位和 Windows GPU 跨机实机闭环，但蓝块叠白块任务未完成。最新状态与下一步见[2026-11-03 交接](../../交接/2026-11-03_单相机叠块与GPU推理/00_接手必读.md)；不要沿用本文“模型尚未实机闭环”的旧结论描述新模型。

## 1. 项目范围

本项目覆盖 SO101 Pro 双臂系统的环境恢复、Leader→Follower 主从遥操作、无相机轨迹录制与回放、自动归位、双相机显示/采集、语音触发和预训练模型探针。当前核心控制链路是：

```text
Leader 主臂 → LeRobot teleoperation → Follower 从臂
                                  ↘ 相机观测/轨迹数据
```

预训练模型链路是独立实验线：Ubuntu 采集观测，Windows GPU 服务推理，结果通过网络返回；它尚未证明真实闭环抓取。

## 2. 系统与身份

| 项目 | 已知历史配置 | 证据边界 |
|---|---|---|
| Windows 工作区 | `D:\具身智能` | 本地文件存在可核对；不等于 Ubuntu 已同步 |
| Ubuntu 运行环境 | Conda `so101`，项目 `~/lerobot` | 历史配置；本快照未重新进入 VM |
| LeRobot | 历史记录 0.6.2；可编辑安装 | 版本和 commit 需在当前 VM 复核 |
| Leader 端口 | 历史 `/dev/ttyACM1` | USB 重插/VM 重启后必须重新枚举 |
| Follower 端口 | 历史 `/dev/ttyACM0` | 同上，不能作为永久身份 |
| Leader 电源 | 历史按套件使用 5V/4A | 以设备标签和当前接线为准 |
| Follower 电源 | 历史按套件使用 12V/2A | 异常运动时应断开电机电源；Ctrl+C 不是急停 |
| 电机 ID | 1 shoulder_pan；2 shoulder_lift；3 elbow_flex；4 wrist_flex；5 wrist_roll；6 gripper | 历史已配置；当前不应盲目重写 |

校准文件历史路径：

```text
~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/leader_arm.json
~/.cache/huggingface/lerobot/calibration/robots/so_follower/follower_arm.json
```

## 3. 已完成工作

### 3.1 基础硬件与环境

- 已安装 LeRobot 及 Feetech 依赖，建立 Ubuntu `so101` 环境。
- 已处理串口权限、USB 透传和 Leader/Follower 端口交换问题。
- 两套机械臂电机 ID、型号 777 和 1,000,000 baud 的配置流程已完成。
- Leader、Follower 均完成过整臂校准；错误输入 F4/F5 后重新完成从臂配置。
- 已确认 F3 问题不是明显机械卡死；诊断脚本能读取目标、实际位置、力矩和状态。

### 3.2 无相机 Demo

- 主从遥操作已由用户实际运行确认。
- 已完成无相机 A→B 搬运 Demo，连续三次成功。
- 已录制本地轨迹并成功回放。
- 已实现 `so101_home.py` 的起点保存、当前位姿保存、检查、归位、Demo、释放等入口。
- 归位流程包含校准 hash、USB 序列号、电机 ID/model、目标寄存器预置、速度限制和异常停止检查。
- 回放路径的 `max_relative_target` 已从 2 调整为 5；用户反馈调整后可正常完成。此参数不是物理速度保证。

历史 Ubuntu 数据位置：

```text
/home/user/lerobot/recordings/so101_pick_place_01
/home/user/lerobot/recordings/so101_pick_place_02
/home/user/lerobot/poses/demo_start.json
/home/user/lerobot/poses/pick_place_02_start.json
```

新轨迹采用 `so101_pick_place_YYYYMMDD_HHMMSS` 模式。Windows 项目目录中的脚本和说明不会自动同步到 Ubuntu；`so101_home.py` 如需使用需手工复制到 `~/lerobot/so101_home.py`。

### 3.3 双相机

- 已接入腕部相机和旁侧/外部相机。
- 已有相机发现、浏览器预览和浏览器显示遥操作脚本。
- 因 Rerun GPU `R32Float` 问题，采用 JPEG 浏览器显示包装器，避免依赖 HighGUI/Rerun 显示路径。
- 历史记录中曾出现 `/dev/video0` 与 `/dev/video2`，但“腕部/外部”角色在不同记录中冲突，必须用当前画面重新确认。

### 3.4 语音与模型实验

- 语音任务一回放流程已有；任务二第三条轨迹的软件绑定、`--dataset2`、`--pose2`、`--check-config`、`--execute` 和 busy reject 已实现。
- 语音助手软件测试历史为 12 项通过；Ubuntu 实际语音链路和第三条轨迹真实执行仍缺少完整回传。
- Windows RTX 5060 Laptop GPU、CUDA、模型服务和通信接口做过软件验证；Ubuntu 真实观测做过只读验证。
- 预训练模型实验中存在肩部/肘部观测偏差；未证明模型稳定控制真实机械臂、完成抓取或握手。

## 4. 已解决问题

| 问题 | 处理 | 当前结论 |
|---|---|---|
| 主从端口交换 | 通过枚举/拔插确认角色 | 解决过；每次重启需重查 |
| 串口权限 | 处理设备访问权限 | 历史解决；当前权限需复核 |
| F4/F5 配置输入错误 | 重新执行对应配置/校准 | 历史已恢复 |
| F3 不跟随 | 只读诊断并检查机械活动范围 | 未发现明显卡死；通信/负载/限位根因未完全闭合 |
| 回放幅度不足或滞后 | 将回放 `max_relative_target` 从 2 改为 5 | 用户反馈可正常完成；仍需量化误差 |
| Rerun `R32Float` | 浏览器 JPEG 显示 | 显示路径绕过；不代表录制链路已验证 |
| VM 重启后环境恢复 | 编写启动 README 和遥操作说明 | 文档已完成；端到端本轮未复测 |

## 5. 当前未完成事项

### P0：硬件与控制证据

1. 在当前 VM/当前插线状态下重新枚举 `/dev/ttyACM*`，确认 Leader/Follower、USB 序列号、权限和校准文件 hash。
2. 对 F3 及整臂跟随滞后做一次只读、可重复的诊断，区分通信延迟、目标限幅、负载/死区和校准问题；在证据充分前不改 PID、ID 或限位。
3. 记录一次从 VM 重启到遥操作的完整日志，包含命令、退出状态和用户动作检查。

### P1：相机与数据

1. 使用当前画面重新确定腕部相机和外部相机角色，不能沿用旧 `/dev/video*` 映射。
2. 单独验证双相机新录制数据集：图像可读、帧数、状态/动作对齐、时间戳和保存路径。
3. 将“浏览器能看到画面”和“录制数据可用于训练”分开验收。

### P2：上层功能

1. 在真实 Ubuntu 环境验证任务二语音一次执行、忙碌拒绝和停止行为。
2. 为预训练模型建立独立实验记录，验证时序、视觉条件差异和动作安全门；不得把推理返回张量视为实机成功。
3. 尚无本地训练收敛、独立实机抓取或握手成功的充分证据。

## 6. 下一步建议

按顺序执行：

1. 只读恢复设备身份和当前状态。
2. 若身份一致，再运行短时低风险遥操作检查跟手性。
3. 固定相机位置并保存当前相机发现结果与画面截图。
4. 录制一条带双相机的数据集，完成离线完整性检查。
5. 再决定是否进入语音、训练或模型闭环实验。

任何异常运动优先断开 Follower 电机电源；不要通过反复放宽限幅、覆盖校准或重写电机 ID 来“通过”测试。

## 7. 主要入口

- [文档索引](INDEX.md)
- [变更时间线](CHANGELOG.md)
- [证据矩阵](EVIDENCE_MATRIX.md)
- [历史会话导出](evidence/2026-10-29/conversation.md)
- [无相机归位脚本](../../../无相机Demo/so101_home.py)
- [双相机遥操作脚本](../../../双相机Demo/teleop_web.py)
- [语音任务助手](../../../语音任务助手/voice_tasks.py)
- [预训练模型当前核对](../../../预训练模型Demo/当前核对结果.md)
