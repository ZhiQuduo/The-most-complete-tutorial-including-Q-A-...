# 架构与接口

维护日期：2026-10-30。实机证据与未验证事项见 [最新交接](handoffs/2026-10-30.md)。

## 进程与设备边界

Windows RTX5060 8GB 在 `D:\具身智能\握手Demo\probe_server.py` 执行 ACT 推理；Ubuntu VMware 负责相机、串口和本地校准。服务端不控制机器人。Windows 解释器为 `D:\具身智能\预训练模型Demo\.venv\Scripts\python.exe`，Ubuntu 使用 `/home/user/lerobot/.venv_policy_probe/bin/python`。

模型：`TommyZihao/lerobot_zihao_model_shake_hands`，revision `e241674c8ee39b451933408900f2683559c181b2`。单幅 RGB front + 六轴状态，输出 100×6 绝对位置候选。front 是键名，作者样本属于腕部视角，不代表桌面俯视。无语言输入或手势触发器。

`/health` 返回模型身份、相机键、形状、协议版本与 motion_enabled=false；`/predict` 使用 [1080,1920,3] 横幅输入；`/predict-portrait` 是 [1920,1080,3] 实验路径，未证明适合实机。

## 文件职责

| 文件 | 行为 |
|---|---|
| start_server.ps1 | Windows 隐藏启动服务、健康检查、复用符合身份的实例、记录 PID/日志 |
| handshake_probe.py | check 枚举与服务检查；preview 仅相机；capture 采图、读状态并请求推理 |
| readonly_arm.py | 拒绝写寄存器、改变力矩及校准；连接不握手，断开保留力矩 |
| camera_transform.py | 旋转；letterbox 保留视场；不能恢复遮挡或改变安装视角 |
| recheck_saved.py | 状态/动作数值坐标换算；不建立物理标定对齐 |
| compare_padding.py | 对同一保存观测比较横幅补边和实验竖幅；不连接电机 |
| wrist_trial.py / joint_trial.py | 默认只读预览；显式 execute 才试动单轴，限幅 1°、限速 0.5°/s |
| handshake_motion_core.py | 已有执行器副本，身份/校准检查、反馈限幅、停止及冻结路径 |
| handshake_motion_guard.py / joint_motion_guard.py | 限制目标、反馈偏移、入口力矩与稳定性 |
| diagnose_hold.py | 只读当前位置/目标/状态及肘腕寄存器，不写目标/PID/力矩 |

## 坐标约定

固定顺序：shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper。当地前五轴以度表示，夹爪为校准范围百分比。电机原始位置每计数约 360/4095 = 0.087912°。

range_m100_100 候选换算：前五轴将本地角度除以校准半量程 `(range_max-range_min)*180/4095` 再乘 100，处理 drive_mode 的方向；反变换用于动作候选。夹爪百分比不变。公式细节以 recheck_saved.py 为准；模型作者训练单位/真实零位仍未独立确认。控制执行器当前只接受其审查过的 drive_mode=0 校准。

## 试动限制

v6/v7 检查 USB 序列号、校准哈希、模型 revision、源观测状态和当前姿态；只取一个关节方向，不执行模型完整动作。其他轴目标保持入口位置。混合力矩状态拒绝执行。入口含稳定性检查和倒计时。

LEAD=0.8°，误差大于 LEAD×0.75=0.6° 持续 1.5 秒停止；结束阈值前五轴 0.4°，夹爪 0.5%。异常尝试把目标冻结到反馈并保留力矩，不保证断电或自动避障。不能带电强扳。

每个 comparison 使用 `wrist_attempt_<sha256前16位>.json` 排他尝试标记，v6/v7 共用，失败也保留。禁止删除标记或循环小步绕过保护。禁止为通过试验直接放宽跟随阈值、提高力矩或更改 PID。核心 SHA256 应保持 `8e0a09db8591030368ea5970aaeb19ad3f464c4b863bcb7a9b57481a96697fe7`。
