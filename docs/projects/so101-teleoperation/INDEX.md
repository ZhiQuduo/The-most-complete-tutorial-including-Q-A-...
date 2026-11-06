# SO101 Teleoperation 文档索引

本目录是面向后续 agent 的规范入口。业务脚本仍保留在工作区原模块目录，证据和状态文档集中在本目录。

## 核心状态

- [PROJECT_STATUS.md](PROJECT_STATUS.md)：当前完成项、已解决问题、未完成事项、风险和下一步。
- [CHANGELOG.md](CHANGELOG.md)：按日期记录安装、校准、故障、Demo、相机和模型实验。
- [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md)：逐项标注来源、状态、真实硬件证据和限制。

## 历史证据

- [conversation.md](evidence/2026-10-29/conversation.md)：截至文档维护请求的父窗口与当前窗口可见消息导出。
- [history-index.json](evidence/2026-10-29/history-index.json)：原始会话路径、SHA256、导出计数和消息索引。
- [artifact-inventory.json](evidence/2026-10-29/artifact-inventory.json)：历史提到的项目文件清单及 hash。

## 业务模块

- [单相机叠块 Demo 目录](../../../单相机叠块Demo/)：自训练 ACT、P=32、自动归位、Windows GPU 跨机推理和最新实机日志。
- [无相机 Demo 目录](../../../无相机Demo/)：`so101_home.py`、轨迹检查、自动归位和录制/回放说明。
- [双相机 Demo 目录](../../../双相机Demo/)：`preview_web.py`、`teleop_web.py` 及浏览器显示说明。
- [语音任务助手目录](../../../语音任务助手/)：语音监听、任务调度、轨迹绑定和测试。
- [预训练模型 Demo 目录](../../../预训练模型Demo/)：Windows 推理服务、Ubuntu 只读探针和当前核对结果。
- [握手 Demo 目录](../../../握手Demo/)：只读诊断、样本对照和动作实验记录。

## 相关全局交接

- [2026-11-03 单相机叠块与 GPU 推理](../../交接/2026-11-03_单相机叠块与GPU推理/00_接手必读.md)
- [SO101 Teleoperation 正式接手摘要](../../handoffs/2026-10-29-so101-teleoperation/HANDOFF.md)
- [项目状态与技术交接](../../handoffs/2026-10-29_SO101项目状态与技术交接.md)
- [VM 启动交接](../../handoffs/2026-10-29_vm-startup-readme.md)
- [当前状态入口](../../status/current.md)
- [根目录遥操作说明](../../../SO101遥操作说明_虚拟机重启后.md)

## 目录约定

```text
so101-teleoperation/
├── PROJECT_STATUS.md
├── CHANGELOG.md
├── EVIDENCE_MATRIX.md
├── INDEX.md
├── evidence/YYYY-MM-DD/   # 不可变历史导出、清单、日志摘要
├── tools/                  # 证据导出和审计工具
└── handoffs/YYYY-MM-DD/    # 面向接手 agent 的阶段性交接（需要时新增）
```

新增硬件验证时使用日期目录，记录命令、原始输出、设备身份和证据限制；不要删除或覆盖历史证据。所有路径均以 `D:\具身智能` 为工作区根目录解析。
