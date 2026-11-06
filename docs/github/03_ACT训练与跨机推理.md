# 双相机 ACT 训练与跨机推理

## 1. 为什么使用双相机

单相机基线已经打通“图像/状态 → Windows GPU → 动作 → Ubuntu 安全执行”，但固定视角无法稳定表达夹爪附近的局部关系。项目没有把第二个图像键硬塞进旧 checkpoint，而是重新采集 front+wrist 同步示范并训练独立 ACT。

训练和部署的视觉合同必须完全一致：

```text
observation.images.front  3×480×640
observation.images.wrist  3×480×640
observation.state         6
action chunk              30×6
```

## 2. 双相机数据采集

完整脚本：[record_dual_camera.sh](../../双相机ACT训练/record_dual_camera.sh)。它用 `/dev/serial/by-id` 和 `/dev/v4l/by-*` 解析设备，不依赖易变的 ACM/video 数字；公开前应把当前设备标识移到环境变量。

先停止其他相机/串口消费者并验证画面：

```bash
export SO101_FOLLOWER_BY_ID=/dev/serial/by-id/REPLACE_ME
export SO101_LEADER_BY_ID=/dev/serial/by-id/REPLACE_ME
export SO101_FRONT_CAMERA=/dev/v4l/by-id/REPLACE_ME
export SO101_WRIST_CAMERA=/dev/v4l/by-id/REPLACE_ME
cd "$HOME/blue_on_white_act/双相机ACT训练"
python verify_dual_cameras.py \
  --front /dev/video4 \
  --wrist /dev/video2 \
  --output "$HOME/lerobot/outputs/dual_camera_check"
```

通过条件：两路均为 `480×640×3`，读取失败为 0，实测至少 24 FPS；人工确认 front/wrist 没有互换，夹爪和两个方块可见。

录制：

```bash
./record_dual_camera.sh smoke   # 3 条验证流程
./record_dual_camera.sh full    # 新建正式 50 条
./record_dual_camera.sh resume  # 中途停止后补足到 50 条
```

录制键位：

- 右方向键：完成并保留当前 episode。
- 左方向键：丢弃并重录当前 episode。
- Esc：停止并保留已经完成的 episode。

只能在终端明确显示 `Recording episode N` 且已经写入至少 1 秒后按键。复位、视频编码或切换条目的间隙按键，会触发“空 episode buffer”错误：

```text
ValueError: You must add one or several frames with add_frame before calling add_episode.
```

这不是相机视频损坏，而是保存时当前 episode 尚无帧。解决方法是遵守按键时机，并用 `resume` 从已完成条目继续，不覆盖原目录。

## 3. 数据检查与清洗

机器审计：

```bash
python audit_dual_dataset.py \
  "$HOME/lerobot/recordings/yellow_on_blue_dual50_20261104" \
  --expected-episodes 50
```

审计内容包括 episode 数、Parquet 帧数、相机键、每条帧数、视频文件和双路完整解码。正式集结果为：

- 50 episodes。
- 20,478 frames，30 FPS。
- `observation.images.front` 解码 20,478 帧。
- `observation.images.wrist` 解码 20,478 帧。
- `passed=true`。

人工抽帧：

```bash
python review_dual_episodes.py \
  "$HOME/lerobot/recordings/yellow_on_blue_dual50_20261104" \
  --output "$HOME/lerobot/outputs/yellow_on_blue_review"
```

每条检查起点、接近、抓取、放置和终点。脏数据标准包括：抓取失败、碰撞、长时间停顿、手进入画面改变场景、相机遮挡/互换、黄色方块没有最终位于蓝色方块上。项目实际对 14 条问题示范进行了剔除/补录，而不是整批重录。

## 4. 复制到 Windows

使用[sync_dual_dataset.ps1](../../双相机ACT训练/sync_dual_dataset.ps1)，脚本拒绝覆盖已存在的目标目录。也可以按当前主机地址手动 `scp`，但仓库文档不应把示例 IP 当永久配置。

```powershell
$RepoRoot = 'C:\path\to\so101-project'
Set-Location "$RepoRoot\双相机ACT训练"
.\sync_dual_dataset.ps1 -VmHost VM_HOST -VmUser ubuntu_user `
  -SshKey "$HOME\.ssh\id_ed25519"

& 'C:\path\to\python.exe' `
  .\audit_dual_dataset.py `
  .\datasets\yellow_on_blue_dual50_20261104 `
  --expected-episodes 50
```

## 5. ACT 训练

完整脚本：[train_dual_act.ps1](../../双相机ACT训练/train_dual_act.ps1)。如果 PowerShell 报“禁止运行脚本”，只对当前进程临时放行，然后务必回到脚本所在目录：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Set-Location 'C:\path\to\so101-project\双相机ACT训练'
Get-Item .\train_dual_act.ps1
```

先做两步 CUDA smoke：

```powershell
.\train_dual_act.ps1 -Smoke
```

正式训练：

```powershell
.\train_dual_act.ps1 -Epochs 8 -BatchSize 4
```

核心等价参数：

```powershell
$args = @(
  '-u', '-m', 'lerobot.scripts.lerobot_train',
  '--policy.type=act', '--policy.device=cuda',
  '--policy.dim_model=256', '--policy.dim_feedforward=1024',
  '--policy.n_encoder_layers=2', '--policy.n_vae_encoder_layers=2',
  '--policy.chunk_size=30', '--policy.n_action_steps=10',
  '--dataset.video_backend=pyav', '--dataset.eval_split=0.2',
  '--batch_size=4', '--num_workers=0',
  '--steps=32764', '--env_eval_freq=0',
  '--policy.push_to_hub=false', '--wandb.enable=false', '--seed=42'
)
```

### 为什么只显示 40 个 episode

原数据仍是 50 条。`--dataset.eval_split=0.2` 按 episode 留出 20% 做验证，因此训练器显示：

```text
40 train + 10 eval
dataset.num_episodes=40
dataset.num_frames=16554
```

它不是少读了 10 条。训练步数按训练子集估算：

```text
floor(20478 × 0.8) × 8 epochs ÷ batch 4 ≈ 32764 steps
```

正式训练约 1 小时 55 分钟结束，15,551,494 个可学习参数，最终保存 `032764/pretrained_model`。训练日志的最低已记录验证损失为 step 30,500 的 `eval_loss=0.1649`；该 step 没有单独保存 checkpoint，因此当前部署使用正常结束时保存的最终 checkpoint。不能用 loss 替代实机成功率。

## 6. 跨机推理职责划分

### Windows

- 加载固定的双相机 checkpoint。
- 使用 CUDA 推理。
- 只暴露 `/health` 和 `/predict`。
- 不导入机器人或串口模块，`motion_enabled=false`。

### Ubuntu

- 独占两路相机和 Follower 串口。
- 读取六维反馈、调用 Windows、校验回复。
- 执行校准边界、训练范围、速率、目标领先量、持续滞后和模型/反馈差保护。
- 归位和 ACT 都验证并保留 ID3 `elbow_flex` P=32。

## 7. 启动 Windows GPU 服务

完整实现：[gpu_inference_server_dual.py](../../双相机ACT训练/gpu_inference_server_dual.py)、[start_gpu_server_dual.ps1](../../双相机ACT训练/start_gpu_server_dual.ps1)。

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Set-Location 'C:\path\to\so101-project\双相机ACT训练'
.\start_gpu_server_dual.ps1 -BindAddress 0.0.0.0 -Port 8092 `
  -Checkpoint 'C:\path\to\pretrained_model' `
  -ExpectedSha256 ('a' * 64)  # 替换为独立记录的批准模型 SHA-256
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8092/health | ConvertTo-Json -Depth 5
```

预期关键字段：

```json
{
  "protocol_version": 2,
  "image_keys": ["front", "wrist"],
  "image_shape": [480, 640, 3],
  "action_shape": [30, 6],
  "motion_enabled": false,
  "state_action_convention": "dataset_native",
  "device": "cuda"
}
```

停止服务时在前台窗口按 `Ctrl+C`。如果它在后台运行，先查询监听 PID，再只停止该 PID：

```powershell
$listener = Get-NetTCPConnection -LocalPort 8092 -State Listen
Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" |
  Select-Object ProcessId, CommandLine
Stop-Process -Id $listener.OwningProcess
```

## 8. 部署和无运动预检

Windows 复制 Ubuntu 端代码和 checkpoint：

```powershell
Set-Location 'C:\path\to\so101-project\双相机ACT训练'
.\deploy_dual_to_vm.ps1 -VmHost VM_HOST -VmUser ubuntu_user `
  -Checkpoint 'C:\path\to\pretrained_model'
```

该步骤只复制文件，不启动机器人。Ubuntu 必须先运行[preflight_dual.py](../../双相机ACT训练/preflight_dual.py)：

公共发布清单不会包含本机的 `start_pose_dual.json`。使用者必须通过自己的已验证轨迹和校准生成起点文件，并放到脚本目录；不得复用另一台机械臂的关节位置、USB serial 或校准哈希。

```bash
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate so101
cd "$HOME/blue_on_white_act"

python preflight_dual.py \
  --checkpoint ./pretrained_model_dual \
  --inference-server http://WINDOWS_HOST:8092 \
  --front-camera /dev/video4 \
  --wrist-camera /dev/video2
```

这个脚本明确不导入电机/串口模块。它保存 `dual_preflight/front.png` 和 `wrist.png`，然后用固定起始状态请求一次 `30×6` 动作。通过条件：

- `passed=true`、动作全为有限数。
- `motion_enabled=false`。
- checkpoint SHA、协议版本、相机键、图像形状和动作形状完全匹配。
- 人工确认两张图片角色正确、现场与训练分布接近。

## 9. 分级实机验证

运行类型：**双相机 ACT 推理 + 真实 Follower 运动**。`--execute` 不是普通测试开关，只有前面所有检查通过才使用。

先导出当前设备身份和已经独立核对的校准哈希：

```bash
export SO101_GPU_SERVER=http://WINDOWS_HOST:8092
export SO101_FOLLOWER_SERIAL=REPLACE_WITH_USB_SERIAL
export SO101_CALIBRATION_SHA256=REPLACE_WITH_64_LOWERCASE_HEX_CHARACTERS
```

先看计划，不访问相机/串口：

```bash
python run_demo_dual.py --seconds 5 --profile commissioning
```

第一次只做 5 秒 commissioning：

```bash
python run_demo_dual.py \
  --seconds 5 \
  --profile commissioning \
  --front-camera /dev/video4 \
  --wrist-camera /dev/video2 \
  --inference-server http://WINDOWS_HOST:8092 \
  --expected-serial "$SO101_FOLLOWER_SERIAL" \
  --execute
```

它先自动归位，再执行有界 ACT；任何阶段失败都停止，不会自动进入后续阶段。5 秒通过且遥测审计无停止事件后，才能逐级使用：

```bash
python run_demo_dual.py --seconds 30  --profile task_trial --execute
python run_demo_dual.py --seconds 180 --profile task_trial --execute
python run_demo_dual.py --seconds 300 --profile extended_trial --execute
```

时长只是最大运行窗口，不会提升模型精度。直接把 5 秒变成 300 秒不能替代相机/起姿/示范分布检查。

## 10. 遥测审计

```bash
python audit_rollout_dual.py \
  "$HOME/lerobot/outputs/yellow_on_blue_dual_rollout_YYYYMMDD_HHMMSS/telemetry.jsonl"
```

重点字段：停止原因、预测块数量、边界投影数量和最大修正、状态到模型动作差、发送目标到反馈误差、实际运动范围、GPU/网络/总推理时间，以及 P=32 是否验证和保留。

项目观测到 Windows 服务推理通常约 13–20 ms，VM 网络往返约 27–44 ms，总推理约 50–73 ms。这个结果支持“网络不是主要慢速原因”，但不等于任何一次运行都不会超时。

