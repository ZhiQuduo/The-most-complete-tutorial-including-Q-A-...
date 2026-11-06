# SO101 项目文档总索引

这是 `D:\具身智能` 的文档入口。接手者先阅读[跨项目当前状态](status/current.md)，再阅读下列主题交接。文档只记录可追溯证据；代码、校准文件、Ubuntu 虚拟机数据和轨迹不因整理而移动。

## 当前入口

- [跨项目当前状态](status/current.md)：当前已证实、待验证与安全阻塞点；具体模块交接是细节来源。
- [单相机叠块、P=32 与 Windows GPU 跨机推理](交接/2026-11-03_单相机叠块与GPU推理/00_接手必读.md)：当前最新工作线；链路已通、物理叠放未完成、下一步为新数据/双相机。
- [SO101 遥操作基础交接](handoffs/2026-10-29-so101-teleoperation/HANDOFF.md)：历史基础链路快照，不覆盖各模块较新交接。
- [SO101 项目状态](projects/so101-teleoperation/PROJECT_STATUS.md)：完成项、已解决问题、未完成项和优先级。
- [证据矩阵](projects/so101-teleoperation/EVIDENCE_MATRIX.md)：每条结论的来源和限制。
- [历史变更时间线](projects/so101-teleoperation/CHANGELOG.md)：按日期记录安装、校准、故障和实验。

## 主题入口

- [2026-11-03 单相机叠块与 GPU 推理](交接/2026-11-03_单相机叠块与GPU推理/00_接手必读.md)
- [无相机回放审计](交接/2026-10-30_无相机回放审计/00_接手必读.md)
- [语音、轨迹与归位](交接/2026-10-30_语音轨迹与归位/00_接手必读.md)
- [双相机与模型](交接/2026-10-30_相机2/00_接手必读.md)
- [握手项目](projects/so101-handshake/README.md)
- [文档扫描与同步审计](status/2026-10-30_项目文档扫描与同步审计.md)
- [虚拟机启动说明](../SO101遥操作说明_虚拟机重启后.md)

## 证据与工具

- [可见消息导出](projects/so101-teleoperation/evidence/2026-10-29/conversation.md)
- [历史索引 JSON](projects/so101-teleoperation/evidence/2026-10-29/history-index.json)
- [文件清单 JSON](projects/so101-teleoperation/evidence/2026-10-29/artifact-inventory.json)
- [证据导出工具](tools/export_thread_evidence.py)

## 维护规则

1. 新交接使用 `交接/YYYY-MM-DD_主题/`，阅读顺序用 `00_`、`01_` 等前缀；本项目级状态放 `projects/<project>/`。
2. 每项实验写明日期、来源、命令、输入、输出、通过标准和局限，并标注 `DONE`、`PARTIAL`、`UNVERIFIED` 或 `BLOCKED`。
3. 用户实测、粘贴日志、脚本测试、静态检查和推断分开记录。旧证据只追加，不覆盖。
4. `/dev/ttyACM*`、`/dev/video*`、USB 序列号、进程和供电状态都是会话级事实；重启或重插后必须重新确认。
5. 不在文档维护任务中启动机械臂、删除轨迹、修改电机 ID、覆盖校准或安装依赖。
