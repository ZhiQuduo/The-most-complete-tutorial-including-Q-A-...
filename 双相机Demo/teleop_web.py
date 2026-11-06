#!/usr/bin/env python3
"""LeRobot 双相机遥操作＋Ubuntu 浏览器画面，关闭 Rerun 显示。

在原 lerobot-teleoperate 参数前使用 python teleop_web.py。
本程序会启动实际遥操作；只有网页服务不直接读取相机或写电机。
"""
import argparse
import logging
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>双相机遥操作</title><style>
body{font:16px sans-serif;background:#18202b;color:#edf2f7;margin:24px}
main{display:flex;gap:20px;flex-wrap:wrap}section{flex:1;min-width:300px}
img{width:100%;max-width:640px;background:#000}small{display:block;margin:8px 0}
</style><h1>双相机遥操作</h1>
<p>机械臂可能正在运动。网页仅显示画面；停止请在控制终端按 Ctrl+C。</p>
<main><section><h2>腕部 / Wrist</h2><small id="wrist_status">等待画面</small>
<img id="wrist" alt="腕部相机"></section>
<section><h2>旁侧 / Side</h2><small id="side_status">等待画面</small>
<img id="side" alt="旁侧相机"></section></main><script>
for(const name of ['wrist','side']){
 const img=document.getElementById(name),status=document.getElementById(name+'_status');
 const refresh=()=>{img.src='/'+name+'.jpg?t='+Date.now()};
 img.onload=()=>{status.textContent='页面最近取图：'+new Date().toLocaleTimeString();setTimeout(refresh,100)};
 img.onerror=()=>{status.textContent='暂无新画面，请查看控制终端';setTimeout(refresh,500)};
 refresh();
}</script></html>""".encode("utf-8")


def prepare_cli(arguments):
    """只强制关闭 Rerun 显示，其余控制参数原样转发。"""
    output, index = [], 0
    while index < len(arguments):
        token = arguments[index]
        if token == "--display_data":
            index += 1
            if index < len(arguments) and not arguments[index].startswith("--"):
                index += 1
            continue
        if not token.startswith("--display_data="):
            output.append(token)
        index += 1
    return output + ["--display_data=false"]


def observation_wrapper(original, publish):
    warned = False

    def wrapped(self, *args, **kwargs):
        nonlocal warned
        observation = original(self, *args, **kwargs)
        try:
            publish(observation)
        except Exception:
            # 显示错误不改变原来的动作或反馈，不额外发电机命令。
            if not warned:
                logging.getLogger(__name__).exception("浏览器画面更新失败；原遥操作反馈继续返回。")
                warned = True
        return observation
    return wrapped


class WebView:
    def __init__(self, port):
        self.port = port
        self.frames = {}
        self.lock = threading.Lock()
        self.last_publish = -float("inf")
        self.server = self.thread = None

    def publish(self, observation):
        now = time.monotonic()
        if now - self.last_publish < 0.1:
            return
        self.last_publish = now
        import cv2
        pending = {}
        for name in ("wrist", "side"):
            image = observation.get(name)
            if image is None:
                continue
            # 命令固定为 LeRobot 默认 RGB，OpenCV JPEG 编码需要 BGR。
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                raise RuntimeError(f"{name} JPEG 编码失败")
            pending[name] = (encoded.tobytes(), time.monotonic())
        with self.lock:
            self.frames.update(pending)

    def start(self):
        view = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path == "/":
                    code, kind, body = 200, "text/html; charset=utf-8", PAGE
                elif path in ("/wrist.jpg", "/side.jpg"):
                    with view.lock:
                        sample = view.frames.get(path[1:-4])
                    if sample is None or time.monotonic() - sample[1] > 2:
                        code, kind, body = 503, "text/plain", b"No fresh observation"
                    else:
                        code, kind, body = 200, "image/jpeg", sample[0]
                else:
                    code, kind, body = 404, "text/plain", b"Not found"
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", kind)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        if self.server:
            if self.thread and self.thread.is_alive():
                self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--web-port", type=int, default=8765)
    args, remaining = parser.parse_known_args()
    from lerobot.robots.so_follower.so_follower import SOFollower
    from lerobot.scripts import lerobot_teleoperate

    view = WebView(args.web_port)
    original = SOFollower.get_observation
    original_argv = sys.argv
    try:
        view.start()
        SOFollower.get_observation = observation_wrapper(original, view.publish)
        sys.argv = [original_argv[0]] + prepare_cli(remaining)
        print(f"在 Ubuntu 浏览器打开 http://127.0.0.1:{args.web_port}", flush=True)
        print("即将按传入参数启动真实遥操作；仅运行本程序，不要另开相机预览。", flush=True)
        lerobot_teleoperate.main()
    finally:
        sys.argv = original_argv
        SOFollower.get_observation = original
        view.close()


if __name__ == "__main__":
    main()
