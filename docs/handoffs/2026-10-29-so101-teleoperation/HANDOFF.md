# SO101 Teleoperation 接手文档

状态日期：2026-10-30（Asia/Shanghai）  
范围：SO101 Pro 双臂、LeRobot 主从遥操作、无相机轨迹、自动归位和相关未闭环实验。

## 1. 先读结论

历史上已完成 Leader/Follower 的电机 ID 配置、整臂校准、主从遥操作和无相机 A→B 搬运；用户报告连续三次手动演示成功。轨迹录制、起点保存、检查、归位和回放流程也已形成。回放限幅从 `2` 改为 `5` 后，用户报告当前轨迹可正常完成。

这些结论是历史用户反馈或脚本证据，不是本次 Windows 文档维护时的现场复测。当前端口、供电、校准 hash、Ubuntu 脚本副本和第 1 条轨迹是否仍存在，均不得假设。

## 2. 环境与设备事实

| 项目 | 历史记录 | 约束 |
|---|---|---|
| Ubuntu | Conda `so101`，`~/lerobot` | 重启后先重新激活并检查目录 |
| LeRobot | 0.6.2 | 当前版本需在 VM 内复核 |
| Leader | 历史 `/dev/ttyACM1`，名称 `leader_arm` | 端口会随重插/重启变化 |
| Follower | 历史 `/dev/ttyACM0`，名称 `follower_arm` | 端口会随重插/重启变化 |
| 电机 | ID 1—6，型号 777，baud 1,000,000 | 不要无证据重写 ID |
| 供电 | Leader 5V/4A；Follower 12V/2A | 以适配器标签和当前接线为准 |

关节映射为：`1 shoulder_pan`、`2 shoulder_lift`、`3 elbow_flex`、`4 wrist_flex`、`5 wrist_roll`、`6 gripper`。历史校准路径为 `~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/leader_arm.json` 和 `~/.cache/huggingface/lerobot/calibration/robots/so_follower/follower_arm.json`。

## 3. 已完成和已解决

- 处理过串口权限、VMware USB 透传、主从端口确认和 F4/F5 输入错误；之后两臂完成校准。
- 主从遥操作曾真实运行；曾出现卡顿和不跟手，约 29.5 Hz 的快照不足以确定根因。
- 无相机手动搬运连续三次成功；第一条轨迹历史记录为 1 episode、1774 frames、约 60 s。
- `无相机Demo/so101_home.py` 已实现 `save-start`、`save-current`、`check`、`home`、`demo`、`release`，并有 16 项软件模拟测试和 Python 编译检查记录。
- 回放限幅 `2` 导致用户观察到滞后/幅度不足；改为 `5` 后用户报告可正常完成。归位内部的 `LEAD=2` 是独立保护参数，不应一起改。

## 4. 数据、脚本和证据位置

历史 Ubuntu 路径：

```text
/home/user/lerobot/recordings/so101_pick_place_01
/home/user/lerobot/recordings/so101_pick_place_02
/home/user/lerobot/poses/demo_start.json
/home/user/lerobot/poses/pick_place_02_start.json
/home/user/lerobot/so101_home.py
```

第 1 条轨迹和起点的 `gio trash` 命令曾提供，但历史中没有执行回执，因此删除状态为 `UNVERIFIED`。Windows 工作区入口为 [so101_home.py](../../../无相机Demo/so101_home.py)、[归位说明](../../../无相机Demo/自动归位使用说明.md) 和 [全流程](../../../无相机Demo/重新录制与自动回放全流程.md)。

原始消息证据位于 [conversation.md](../../projects/so101-teleoperation/evidence/2026-10-29/conversation.md)，项目判断见 [PROJECT_STATUS.md](../../projects/so101-teleoperation/PROJECT_STATUS.md) 和 [EVIDENCE_MATRIX.md](../../projects/so101-teleoperation/EVIDENCE_MATRIX.md)。

## 5. 未完成事项

| 优先级 | 状态 | 最小下一步 |
|---|---|---|
| P0 | `UNVERIFIED` 当前设备身份 | Ubuntu 内运行 `python -m serial.tools.list_ports -v`，逐板确认角色、权限、校准文件和序列号 |
| P0 | `UNVERIFIED` Ubuntu 是否同步限幅 5 | 现场查看 `~/lerobot/so101_home.py` 或实际回放命令，不从 Windows 文件推断 |
| P0 | `PARTIAL` F3 跟踪失败根因 | 只读记录三次目标、反馈、力矩、状态；不先改 PID、ID、限位或阈值 |
| P1 | `UNVERIFIED` 回放误差量化 | 固定起点做至少三次，分别记录时滞、幅度和末端位置 |
| P1 | `UNVERIFIED` 双相机录制链路 | 重新枚举相机、看画面确认角色，再检查图像/状态/动作对齐和写盘 |
| P2 | `UNVERIFIED` 语音任务二实机闭环 | 核对第三条轨迹与起点，验证一次执行、忙碌拒绝和停止行为 |
| P2 | `UNVERIFIED` 视觉自主抓取/握手 | 先完成只读推理与安全门，再用独立实验记录实机成功率；不能由模型输出张量代替 |

## 6. 接手顺序和安全边界

1. 在 Ubuntu 新终端执行 `conda activate so101`、`cd ~/lerobot`，确认没有旧的 teleoperate/replay 进程。
2. 重新枚举两块 USB 并通过逐板拔插确认 Leader/Follower；不要直接使用历史 ACM 编号。
3. 先做只读检查或小幅预览；底座固定、夹爪空载、前臂有支撑、路径无遮挡。
4. 发生异响、异常运动或失控时，优先切断 Follower 12V 电源；`Ctrl+C` 和语音停止都不是硬件急停。
5. Windows 脚本不会自动同步到 Ubuntu；复制后先运行 `--help` 和静态检查，再决定是否进行真实运动。

## 7. 证据标签

- `DONE`：有直接用户设备反馈或完整日志支持。
- `PARTIAL`：部分链路成立，仍有明确缺口。
- `UNVERIFIED`：只有历史记录、代码、计划或当前无法访问的 Ubuntu 状态。
- `BLOCKED`：因设备或外部条件无法继续；不得用推断填补。

本文件只维护项目交接信息，不执行设备控制、不删除轨迹、不修改校准。
