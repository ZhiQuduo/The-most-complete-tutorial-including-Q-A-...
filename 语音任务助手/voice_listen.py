#!/usr/bin/env python3
"""Ubuntu 中文语音口令测试。仅显示匹配结果，不导入 LeRobot、不访问串口。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

DEFAULT_SOURCE = "alsa_input.pci-0000_02_02.0.analog-stereo"
COMMANDS = {
    "执行任务一": "task_1",
    "完成任务一": "task_1",
    "查询状态": "status",
    "停止任务": "stop",
}


def match_command(text):
    normalized = re.sub(r"[\s，。！？、,.!?]", "", text).replace("1", "一")
    return COMMANDS.get(normalized)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True, help="解压后的 Vosk 中文模型目录")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="pactl 列出的麦克风 source 名称")
    args = parser.parse_args()
    if not (args.model / "am/final.mdl").is_file():
        parser.error("模型目录不正确，应直接包含 am/final.mdl；请先下载并解压模型。")
    if not shutil.which("parec"):
        parser.error("找不到 parec。请在已完成录音测试的 Ubuntu 内运行。")
    try:
        from vosk import KaldiRecognizer, Model, SetLogLevel
    except ImportError:
        parser.error("当前 Python 未安装 vosk；请先激活 so101_voice 环境。")
    SetLogLevel(-1)
    print("正在加载模型……", flush=True)
    rec = KaldiRecognizer(Model(str(args.model.resolve())), 16000)
    # 使用已经实测通过的 PulseAudio 输入；输出为 16 kHz、16-bit、单声道 PCM。
    process = subprocess.Popen(
        ["parec", "--device=" + args.source, "--raw", "--format=s16le",
         "--rate=16000", "--channels=1"],
        stdout=subprocess.PIPE,
    )
    last_command, last_time = None, 0.0
    try:
        print("语音测试已启动；本程序不会驱动机械臂。", flush=True)
        print("请说：执行任务一 / 完成任务一 / 查询状态 / 停止任务。Ctrl+C 退出。", flush=True)
        while True:
            data = process.stdout.read(4000)
            if not data:
                raise RuntimeError("麦克风音频流结束，请检查上方的 parec 错误和设备连接。")
            # 只处理整句结果，不用尚未确定的局部识别结果触发口令。
            if not rec.AcceptWaveform(data):
                continue
            text = json.loads(rec.Result()).get("text", "").strip()
            if not text:
                continue
            print("识别文字：" + text, flush=True)
            command = match_command(text)
            if command is None:
                print("未匹配固定口令。", flush=True)
                continue
            now = time.monotonic()
            if command == last_command and now - last_time < 3:
                print("忽略短时间内重复口令。", flush=True)
                continue
            last_command, last_time = command, now
            if command == "task_1":
                print("【测试通过】匹配任务一；尚未绑定运动命令。", flush=True)
            elif command == "status":
                print("【状态】语音测试待命；机械臂未连接。", flush=True)
            else:
                print("【停止口令】已识别；当前没有运行中的机械臂任务。", flush=True)
    except KeyboardInterrupt:
        print("\n语音测试结束。", flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        process.stdout.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("错误：" + str(error), file=sys.stderr)
        raise SystemExit(1)
