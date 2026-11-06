#!/usr/bin/env python3
"""Ubuntu 中文口令启动 SO101 任务一/二/三；每项独立绑定轨迹与起点。"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

SOURCE = "alsa_input.pci-0000_02_02.0.analog-stereo"


def say(text):
    print(time.strftime("[%H:%M:%S] ") + text, flush=True)


def intent(text):
    text = re.sub(r"[\s，。！？、,.!?]", "", text).replace("1", "一").replace("2", "二").replace("3", "三")
    return {"执行任务一": "start", "完成任务一": "start",
            "执行任务二": "start2", "完成任务二": "start2",
            "执行任务三": "start3", "完成任务三": "start3", "请完成任务三": "start3",
            "查询状态": "status", "停止任务": "stop"}.get(text)


def task_args(args, task):
    if task == 1:
        return args
    if task not in (2, 3):
        raise ValueError("任务编号不支持。")
    pose = getattr(args, f"pose{task}", None)
    dataset = getattr(args, f"dataset{task}", None)
    if not pose or not dataset:
        raise ValueError(f"任务{task}尚未配置配套起点和轨迹目录。")
    return SimpleNamespace(**{**vars(args), "pose": pose, "dataset": dataset})


def validate(args):
    for path in (args.robot_python, args.helper, args.pose, args.dataset / "meta/info.json"):
        if not path.is_file():
            raise ValueError(f"找不到文件：{path}")
    profile = json.loads(args.pose.read_text(encoding="utf-8"))
    binding = profile.get("dataset") or {}
    if Path(binding.get("root", "")).expanduser().resolve() != args.dataset.resolve():
        raise ValueError("起点绑定的轨迹与当前任务数据目录不同，请核对，不能混用起点。")
    if binding.get("episode") != 0 or not binding.get("repo_id"):
        raise ValueError("起点的轨迹绑定缺少 repo_id 或不是 episode 0。")
    if profile.get("robot_id") != "follower_arm" or profile.get("use_degrees") is not True:
        raise ValueError("起点的机械臂名称或单位不符合现有任务配置。")
    if not Path(args.port).exists():
        raise ValueError(f"从臂端口不存在：{args.port}。请核对 USB 连接和本次端口。")


class Runner:
    def __init__(self, args):
        self.args = args
        self.child = None
        self.stopping = False
        self.blocked = False
        self.ready_after = 0.0
        self.active_task = None

    def poll(self):
        if self.child is None or self.child.poll() is None:
            return False
        code = self.child.returncode
        self.child.wait()
        self.child = None
        self.ready_after = time.monotonic() + 3
        if self.stopping or code != 0:
            self.blocked = True
            say(f"任务停止或异常退出（退出码 {code}）。已锁定启动；检查现场后退出并重开程序。")
        else:
            say("任务流程正常结束。请确认物体已放下，并重新摆放后再下达口令。3 秒后恢复待命。")
        self.stopping = False
        self.active_task = None
        return True

    def start(self, task=1):
        if self.child is not None or self.blocked or time.monotonic() < self.ready_after:
            say("当前正在执行、冷却或已锁定，忽略启动口令；不会排队。")
            return
        try:
            chosen = task_args(self.args, task)
            validate(chosen)
        except (ValueError, OSError, KeyError) as error:
            say(f"拒绝启动任务{task}：{error}")
            return
        if not self.args.execute:
            say(f"【模拟】收到任务{task}；起点 {chosen.pose}；未传 --execute，不启动机械臂。")
            self.ready_after = time.monotonic() + 3
            return
        command = [str(self.args.robot_python), "-u", str(self.args.helper), "demo",
                   "--port", self.args.port, "--pose", str(chosen.pose), "--execute"]
        env = dict(os.environ, HF_HUB_OFFLINE="1", PYTHONUNBUFFERED="1")
        # 语音环境的 Python 路径不能污染机械臂环境。
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        env["CONDA_PREFIX"] = str(self.args.robot_python.parent.parent)
        env["PATH"] = str(self.args.robot_python.parent) + os.pathsep + env.get("PATH", "")
        say(f"启动任务{task}：{chosen.dataset}；归位 → 回放 → 归位。请观察机械臂。")
        self.child = subprocess.Popen(command, cwd=str(self.args.helper.parent),
                                      env=env, start_new_session=True)
        self.active_task = task

    def stop(self):
        # 停止同时锁定，避免后续误识别立刻重新启动。
        self.blocked = True
        if self.child is None:
            say("当前没有运行任务；已锁定启动，退出重开后恢复。")
            return
        self.stopping = True
        try:
            os.killpg(self.child.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        say("已向任务和回放子进程发送中断请求。异常运动请切断 F 电机电源。")

    def status(self):
        state = ("正在停止" if self.stopping else "任务执行中") if self.child else (
            "启动已锁定" if self.blocked else "冷却中" if time.monotonic() < self.ready_after else "待命")
        say("当前状态：" + state + (f"（任务{self.active_task}）" if self.active_task else ""))

    def close(self):
        if self.child is not None:
            self.stop()
            try:
                self.child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                say("任务未在 8 秒内退出，程序将等待它退出，不再接受新任务。必要时切断 F 电源。")
                self.child.wait()


def shortcut(args):
    result = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True)
    desktop = Path(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    path = desktop / "SO101-Voice-Tasks.desktop"
    def quote(value):
        value = str(value).replace("%", "%%")
        for old, new in (("\\", "\\\\"), ('"', '\\"'), ("`", "\\`"), ("$", "\\$")):
            value = value.replace(old, new)
        return '"' + value + '"'
    words = [sys.executable, str(Path(__file__).resolve()), "--execute", "--port", args.port,
             "--robot-python", str(args.robot_python), "--helper", str(args.helper),
             "--pose", str(args.pose), "--dataset", str(args.dataset), "--source", args.source,
             "--pose2", str(args.pose2), "--dataset2", str(args.dataset2),
             "--model", str(args.model)]
    if getattr(args, "pose3", None) and getattr(args, "dataset3", None):
        words += ["--pose3", str(args.pose3), "--dataset3", str(args.dataset3)]
    content = ("[Desktop Entry]\nType=Application\nName=SO101 语音任务助手\n"
               "Comment=语音触发已配置任务：归位、回放、归位\nTerminal=true\n"
               "Icon=audio-input-microphone\nExec=" + " ".join(quote(w) for w in words) + "\n")
    if path.exists() and path.read_text(encoding="utf-8") != content:
        if path.is_symlink():
            raise ValueError("快捷方式是符号链接，未修改。")
        backup = path.with_name(path.name + f".bak_{time.time_ns()}")
        with backup.open("xb") as stream:
            stream.write(path.read_bytes())
        say(f"原快捷方式已备份：{backup}")
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)
    say(f"快捷方式已创建：{path}。如桌面提示不可信，请右键选择“允许启动”。")


def main():
    home = Path.home()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="本次已确认的 F 从臂端口")
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--robot-python", type=Path, default=Path(sys.prefix).parent / "so101/bin/python")
    parser.add_argument("--helper", type=Path, default=home / "lerobot/so101_home.py")
    parser.add_argument("--pose", type=Path, default=home / "lerobot/poses/pick_place_02_start.json")
    parser.add_argument("--dataset", type=Path, default=home / "lerobot/recordings/so101_pick_place_02")
    parser.add_argument("--pose2", type=Path, default=home / "lerobot/poses/pick_place_03_start.json")
    parser.add_argument("--dataset2", type=Path, default=home / "lerobot/recordings/so101_pick_place_03")
    parser.add_argument("--pose3", type=Path, help="任务三专属起点；必须与 --dataset3 一起提供")
    parser.add_argument("--dataset3", type=Path, help="任务三实际轨迹目录；不自动选择最新录制")
    parser.add_argument("--model", type=Path, default=home / "so101_voice/models/vosk-model-small-cn-0.22")
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--install-shortcut", action="store_true")
    parser.add_argument("--execute", action="store_true", help="允许语音口令启动实际任务")
    args = parser.parse_args()
    if bool(args.pose3) != bool(args.dataset3):
        parser.error("任务三必须同时提供 --dataset3 和 --pose3；未打开串口。")
    validate(args)
    say(f"任务一绑定：{args.dataset}；起点：{args.pose}")
    second_error = None
    try:
        second = task_args(args, 2)
        validate(second)
        say(f"任务二绑定：{second.dataset}；起点：{second.pose}")
    except (ValueError, OSError, KeyError) as error:
        second_error = error
        say(f"任务二配置未通过，不能执行任务二：{error}；任务一配置仍有效。")
    third_error = None
    if args.dataset3 is not None:
        try:
            third = task_args(args, 3)
            validate(third)
            say(f"任务三绑定：{third.dataset}；起点：{third.pose}")
        except (ValueError, OSError, KeyError) as error:
            third_error = error
            say(f"任务三配置未通过，不能执行任务三：{error}")
    else:
        say("任务三未配置，不会执行任务三；不影响已有任务。")
    if args.check_config:
        if second_error is not None:
            raise ValueError("任务二配置检查失败，请核对第三套轨迹与配套起点文件。未打开串口。")
        if third_error is not None:
            raise ValueError("任务三配置检查失败，请核对本次录制与专属起点。未打开串口。")
        say("配置文件检查通过；未打开串口。实际校准、USB 身份和归位检查由现有任务程序执行。")
        return
    if args.install_shortcut:
        shortcut(args)
        return
    if not shutil.which("parec") or not (args.model / "am/final.mdl").is_file():
        raise ValueError("找不到 parec 或中文模型目录，请核对已完成的语音环境。")
    import fcntl
    from vosk import Model, KaldiRecognizer, SetLogLevel
    lock_path = home / "so101_voice/.task_controller.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("已经有一个语音任务助手在运行，请先关闭原窗口。")
        SetLogLevel(-1)
        rec = KaldiRecognizer(Model(str(args.model)), 16000)
        runner = Runner(args)
        mic = subprocess.Popen(["parec", "--device=" + args.source, "--raw", "--format=s16le",
                                "--rate=16000", "--channels=1"], stdout=subprocess.PIPE)
        def terminate(signum, frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, terminate)
        say("实际执行模式" if args.execute else "模拟模式：仅显示口令，不运动")
        say("已待命。请按所选任务恢复场景，确保夹爪空载、归位及回放路径无遮挡。")
        say("支持：执行任务一 / 执行任务二 / 请完成任务三 / 查询状态 / 停止任务。Ctrl+C 退出。")
        try:
            while True:
                if runner.poll():
                    rec.Reset()
                if mic.poll() is not None:
                    raise RuntimeError("麦克风进程退出，已停止监听。")
                if not select.select([mic.stdout], [], [], 0.1)[0]:
                    continue
                data = os.read(mic.stdout.fileno(), 4000)
                if not data:
                    raise RuntimeError("麦克风音频流结束。")
                if not rec.AcceptWaveform(data):
                    continue
                text = json.loads(rec.Result()).get("text", "").strip()
                if not text:
                    continue
                say("识别：" + text)
                action = intent(text)
                if action == "start":
                    runner.start()
                elif action == "start2":
                    runner.start(2)
                elif action == "start3":
                    runner.start(3)
                elif action == "stop":
                    runner.stop()
                elif action == "status":
                    runner.status()
        except KeyboardInterrupt:
            say("正在退出语音助手。")
        finally:
            if mic.poll() is None:
                mic.terminate()
            try:
                mic.wait(timeout=3)
            except subprocess.TimeoutExpired:
                mic.kill()
                mic.wait()
            mic.stdout.close()
            runner.close()
        say("语音助手已退出。电机可能仍保持上力；按原流程支撑并卸力。")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        say("停止：" + str(error))
        raise SystemExit(1)
