# SO-101 Pro：从组装、遥操作到双相机 ACT 跨机推理

这是一个基于 **SO-101 Pro、LeRobot、Ubuntu VMware 与 Windows CUDA** 的阶段性机器人项目。项目从散件组装和电机配置开始，先完成主从臂遥操作，再实现轨迹录制/归位/回放、中文语音任务触发，最后采集 50 条双相机示范、训练 ACT，并将相机与实机控制留在 Ubuntu、GPU 推理放在 Windows。

当前视觉任务是：**抓取黄色方块并放到蓝色方块上**。

> 重要：本仓库包含真实机械臂控制代码。默认只读检查、软件测试或推理服务返回动作，都不等于可以安全地启动机械臂。执行运动前必须固定底座、清空路径、确认校准和设备身份，并保证 Follower 电源开关可立即触达。`Ctrl+C` 和语音“停止任务”都不是硬件急停。

## 项目成果

| 阶段 | 结果 | 主要入口 |
| --- | --- | --- |
| 环境与硬件 | Ubuntu 22.04、Conda `so101`、LeRobot；Leader/Follower 各自完成 1–6 号电机配置和校准 | [开机恢复说明](SO101遥操作说明_虚拟机重启后.md) |
| 遥操作 | Leader 控制 Follower；30 Hz；位置单步限幅 5 | [完整遥操作/回放流程](无相机Demo/遥操作到回放完整代码_统一限幅5.md) |
| 轨迹回放 | 保存 episode、记录起始姿态、受控归位、空载回放、带物体回放 | [无相机 Demo](无相机Demo) |
| 语音系统 | Vosk 中文离线识别；任务一、二、三独立绑定；支持模拟、配置检查和真实执行 | [语音任务助手](语音任务助手/README.md) |
| 双相机数据 | 固定全局相机 + 腕部相机；50 episodes、20,478 frames、30 FPS；双路视频审计通过 | [双相机 ACT 工作流](双相机ACT训练/README.md) |
| ACT 训练 | 40 条训练、10 条验证；ACT 15.55M 参数；32,764 steps；约 8 epochs | [训练说明](docs/github/03_ACT训练与跨机推理.md) |
| 跨机推理 | Ubuntu 独占相机/串口/安全控制；Windows RTX GPU 只做双图像 ACT 推理 | [跨机推理说明](docs/github/03_ACT训练与跨机推理.md) |

## 文档导航

- [项目总结与时间线](docs/github/01_项目总结与时间线.md)
- [遥操作、轨迹回放与语音系统操作手册](docs/github/02_操作手册_遥操作回放语音.md)
- [双相机 ACT 训练与跨机推理](docs/github/03_ACT训练与跨机推理.md)
- [问题清单与解决方案](docs/github/04_问题清单与解决方案.md)
- [验证边界、安全说明与 GitHub 发布清单](docs/github/05_证据边界与发布清单.md)
- [历史审计和交接文档](docs/README.md)

## 系统架构

```text
Leader SO-101 ──USB──┐
Follower SO-101 ─USB─┼─ Ubuntu 22.04 VM
front camera ──USB───┤    ├─ 设备身份/校准
wrist camera ──USB───┘    ├─ 30 Hz 观测与安全保护
                           ├─ 遥操作/录制/回放
                           └─ HTTP: front+wrist+state
                                      │
                                      ▼
                             Windows + RTX CUDA
                             双相机 ACT 推理服务
                                      │
                                      └─ 30×6 动作块
```

设计原则是 **Windows 服务永不连接串口，也不具备运动权限**；Ubuntu 在发送目标前完成模型身份、相机、校准、边界、速度、目标/反馈差和 ID3 肘部 P=32 检查。

## 快速入口

设备路径必须按当前会话重新确认。`/dev/ttyACM*` 和 `/dev/video*` 在重插、重启或 VMware 重新分配后可能变化。

### Ubuntu 恢复环境

```bash
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate so101
cd "$HOME/lerobot"
python -m serial.tools.list_ports -v
```

### 启动遥操作（会运动）

```bash
F_PORT=/dev/ttyACM0   # 仅示例，先识别
L_PORT=/dev/ttyACM1   # 仅示例，先识别

lerobot-teleoperate \
  --robot.type=so101_follower \
  --robot.port="$F_PORT" \
  --robot.id=follower_arm \
  --robot.max_relative_target=5 \
  --robot.disable_torque_on_disconnect=false \
  --teleop.type=so101_leader \
  --teleop.port="$L_PORT" \
  --teleop.id=leader_arm \
  --fps=30 \
  --display_data=false
```

### 双相机数据与训练

```bash
# Ubuntu：先导出本机设备配置，再验证相机、录 3 条 smoke、录/补足 50 条
export SO101_FOLLOWER_BY_ID=/dev/serial/by-id/REPLACE_ME
export SO101_LEADER_BY_ID=/dev/serial/by-id/REPLACE_ME
export SO101_FRONT_CAMERA=/dev/v4l/by-id/REPLACE_ME
export SO101_WRIST_CAMERA=/dev/v4l/by-id/REPLACE_ME
cd "$HOME/blue_on_white_act/双相机ACT训练"
python verify_dual_cameras.py --front /dev/video4 --wrist /dev/video2 \
  --output "$HOME/lerobot/outputs/dual_camera_check"
./record_dual_camera.sh smoke
./record_dual_camera.sh full
./record_dual_camera.sh resume
```

```powershell
# Windows：先做 2-step smoke，再正式训练
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$RepoRoot = 'C:\path\to\so101-project'
Set-Location "$RepoRoot\双相机ACT训练"
.\train_dual_act.ps1 -Smoke
.\train_dual_act.ps1 -Epochs 8 -BatchSize 4
```

### 跨机推理

Windows：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$RepoRoot = 'C:\path\to\so101-project'
$Checkpoint = 'C:\path\to\pretrained_model'
$Sha256 = 'a' * 64  # 替换为独立记录的批准模型 SHA-256
Set-Location "$RepoRoot\双相机ACT训练"
.\start_gpu_server_dual.ps1 -BindAddress 0.0.0.0 -Port 8092 `
  -Checkpoint $Checkpoint -ExpectedSha256 $Sha256
```

Ubuntu 先执行无运动预检：

```bash
cd "$HOME/blue_on_white_act"
python preflight_dual.py \
  --inference-server http://WINDOWS_HOST:8092 \
  --front-camera /dev/video4 \
  --wrist-camera /dev/video2
```

只有预检返回 `passed: true`、`motion_enabled: false`、模型哈希/双相机键/30×6 动作形状均一致，并人工确认两张相机图后，才进入实机分级验证。运动命令见[跨机推理章节](docs/github/03_ACT训练与跨机推理.md)，不要直接跳到 300 秒。

## 仓库目录

```text
单相机叠块Demo/      早期单相机 ACT、自动归位与安全诊断基线
双相机ACT训练/       当前双相机采集、审计、训练、部署、推理和保护代码
双相机Demo/          双相机浏览器预览与遥操作显示
无相机Demo/          轨迹录制、起点保存、归位和回放
语音任务助手/        Vosk 识别与任务一/二/三执行器
握手Demo/            更早期预训练模型/双机协议实验
预训练模型Demo/      Windows Python/CUDA 环境及早期服务代码
docs/                历史证据、交接、状态和 GitHub 总结
```

## 当前证据边界

- 双相机数据完整性、训练结束、checkpoint 保存、跨机协议和多次保护停止有日志证据。
- 5 秒 commissioning 链路跑通；之后用户观察到一次成功抓起黄色方块，但在夹爪接触反馈保护处停止。
- “持续运行到时间结束”或“跟踪误差稳定”不等于“成功完成叠放”。目前没有足够的重复成功率统计，因此不声明最终任务已经稳定完成。
- ID3 `elbow_flex` 的 P=32 是本项目明确保留的设备参数；I/D 与力矩限制未因 ACT 调试而提高。



