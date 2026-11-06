# SO101 中文语音任务助手：第一阶段

2026-11-02：维护源已支持“请完成任务三 / 完成任务三 / 执行任务三”，通过独立 `--dataset3` / `--pose3` 绑定，不覆盖任务一、二。任务三没有猜测默认路径，未配置时拒绝执行。当前录制及新版运行命令见[任务三语音回放使用说明](任务三语音回放使用说明.md)。

新增双任务版：`voice_tasks.py` 支持“执行任务二”启动第三条数据 `so101_pick_place_20261015_183432`；任务一仍是第二条数据。复制与运行步骤见《新增任务二_第三条轨迹.md》。为避免误绑定未知轨迹，代码默认值仍是保守占位路径；实际运行任务二必须显式传入 `--dataset2` / `--pose2`，并先执行 `--check-config`。

现已新增 `voice_tasks.py`，用于语音绑定现有归位与回放流程。**按用户最新选择，任务一绑定第 2 套轨迹和 `pick_place_02_start.json`**；详见同目录《任务一语音回放使用说明.md》。下文仅描述最初的识别测试程序。

下面的“仅识别”说明适用于 `voice_listen.py`，不是任务执行器 `voice_tasks.py`。后者在显式传入 `--execute` 后会通过现有 helper 启动真实归位和回放。

Windows 目录里的文件需要复制到 Ubuntu 后运行。Ubuntu 已由用户实测完成麦克风录制及播放；其音频输入名已作为默认值写入脚本。若后续设备变化，用 `pactl list short sources` 核对，再通过 `--source` 指定输入。

## Ubuntu 安装

语音识别使用独立环境，机械臂继续使用原 so101 环境。

```bash
conda create -n so101_voice python=3.10 -y
conda activate so101_voice
python -m pip install vosk
python -c "from importlib.metadata import version; import vosk; print('Vosk 安装成功：', version('vosk'))"
```

## 下载官方中文小模型

```bash
mkdir -p ~/so101_voice/models
cd ~/so101_voice/models
wget -c https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
python -m zipfile -e vosk-model-small-cn-0.22.zip .
```

把本目录的 `voice_listen.py` 复制到 Ubuntu 的 `~/so101_voice/`，执行：

```bash
conda activate so101_voice
python ~/so101_voice/voice_listen.py --model ~/so101_voice/models/vosk-model-small-cn-0.22
```

说“执行任务一”或“完成任务一”，停顿等待整句结果，预期输出“匹配任务一；尚未绑定运动命令”。也可测试“查询状态”“停止任务”。按 Ctrl+C 退出。

识别器可能将中文拆分为空格或把“一”写为“1”，程序会统一处理。仅完全匹配的整句口令被接受；其他内容只显示，不触发。3 秒内同一口令重复结果会被忽略。这些规则不能保证没有误识别；正式接入运动前需实测口令与非口令表现。

后续绑定必须指定实际录制路径、段号和已验证的归位/回放命令，不能凭目录修改时间自动选择轨迹；运行中禁止重复启动。语音停止只能作为辅助，不能替代硬件急停。

## 验证范围

已在 Windows 检查 Python 语法及口令匹配逻辑。尚未在用户 Ubuntu 内安装 Vosk、加载模型或实测识别，未执行任何机械臂运动。

## 官方资料

- https://alphacephei.com/vosk/install
- https://alphacephei.com/vosk/models
- https://github.com/alphacep/vosk-api/blob/master/python/example/test_microphone.py
