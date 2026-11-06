"""Ubuntu 实时口令测试；仅显示识别结果，不访问机械臂。"""
import json
from pathlib import Path
import re
import subprocess
from vosk import Model, KaldiRecognizer, SetLogLevel

SetLogLevel(-1)
model_path = Path.home() / "so101_voice/models/vosk-model-small-cn-0.22"
recognizer = KaldiRecognizer(Model(str(model_path)), 16000)
source = "alsa_input.pci-0000_02_02.0.analog-stereo"
commands = {"执行任务一": "任务一", "完成任务一": "任务一",
            "查询状态": "查询状态", "停止任务": "停止任务"}
mic = subprocess.Popen(
    ["parec", "--device=" + source, "--raw", "--format=s16le",
     "--rate=16000", "--channels=1"], stdout=subprocess.PIPE)
try:
    print("开始聆听。请说：执行任务一。说完停顿 2 秒。Ctrl+C 退出。", flush=True)
    while True:
        data = mic.stdout.read(4000)
        if not data:
            raise RuntimeError("录音流已结束，请查看上方音频设备错误。")
        if not recognizer.AcceptWaveform(data):
            continue
        text = json.loads(recognizer.Result()).get("text", "")
        if not text:
            continue
        print("识别文字：", text, flush=True)
        normalized = re.sub(r"[\s，。！？、,.!?]", "", text).replace("1", "一")
        if normalized in commands:
            print("【匹配成功】" + commands[normalized] + "（当前仅测试）", flush=True)
        else:
            print("未匹配固定口令，请重说。", flush=True)
except KeyboardInterrupt:
    print("\n语音测试结束。", flush=True)
finally:
    if mic.poll() is None:
        mic.terminate()
    try:
        mic.wait(timeout=3)
    except subprocess.TimeoutExpired:
        mic.kill()
        mic.wait()
    mic.stdout.close()
