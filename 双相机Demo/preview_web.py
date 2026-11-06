#!/usr/bin/env python3
"""在 Ubuntu 浏览器预览两台 USB 相机，不依赖 OpenCV HighGUI，不控制机械臂。"""
import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>双相机预览</title><style>
body{font:16px sans-serif;background:#18202b;color:#edf2f7;margin:24px}
main{display:flex;gap:20px;flex-wrap:wrap}section{flex:1;min-width:300px}
img{width:100%;max-width:640px;background:#000}small{display:block;margin:8px 0}
</style><h1>双相机预览</h1><p>只读取相机，不驱动机械臂。结束时在终端按 Ctrl+C。</p>
<main><section><h2>腕部 / Wrist</h2><small id="wrist_status">等待画面</small>
<img id="wrist" alt="腕部相机画面"></section>
<section><h2>旁侧 / Side</h2><small id="side_status">等待画面</small>
<img id="side" alt="旁侧相机画面"></section></main>
<script>
for(const name of ['wrist','side']){
  const img=document.getElementById(name),status=document.getElementById(name+'_status');
  const refresh=()=>{img.src='/'+name+'.jpg?t='+Date.now()};
  img.onload=()=>{status.textContent='最近画面：'+new Date().toLocaleTimeString();setTimeout(refresh,100)};
  img.onerror=()=>{status.textContent='暂时没有新画面，请查看终端';setTimeout(refresh,500)};
  refresh();
}
</script></html>""".encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wrist", default="/dev/video0")
    parser.add_argument("--side", default="/dev/video2")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.wrist == args.side:
        parser.error("两路相机路径必须不同")
    import cv2

    stop, lock = threading.Event(), threading.Lock()
    latest, workers = {}, []

    def capture(name, cap):
        received = False
        try:
            while not stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    if received:
                        print(name, "取帧失败；等待恢复。", flush=True)
                        received = False
                    stop.wait(0.1)
                    continue
                ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not ok:
                    raise RuntimeError(f"{name} JPEG 编码失败")
                if not received:
                    print(name, "已读到画面：", frame.shape, flush=True)
                    received = True
                with lock:
                    latest[name] = (jpeg.tobytes(), time.monotonic())
        except Exception as exc:
            print(f"{name} 采集停止：{exc}", flush=True)
        finally:
            cap.release()
            with lock:
                latest.pop(name, None)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                code, kind, body = 200, "text/html; charset=utf-8", PAGE
            elif path in ("/wrist.jpg", "/side.jpg"):
                name = path[1:-4]
                with lock:
                    sample = latest.get(name)
                if sample is None or time.monotonic() - sample[1] > 2:
                    code, kind, body = 503, "text/plain; charset=utf-8", b"No fresh camera frame"
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

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    try:
        for name, path in (("wrist", args.wrist), ("side", args.side)):
            cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap.release()
                raise RuntimeError(f"无法打开 {path}，请检查 USB 连接、权限和设备占用")
            try:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 15)
                print(name, path, "驱动返回参数：",
                      cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
                      cap.get(cv2.CAP_PROP_FPS), flush=True)
                worker = threading.Thread(target=capture, args=(name, cap), daemon=True)
                worker.start()
                workers.append(worker)
            except BaseException:
                cap.release()
                raise
        print(f"请在 Ubuntu 的浏览器打开：http://127.0.0.1:{args.port}", flush=True)
        print("终端按 Ctrl+C 停止并释放相机；开始 LeRobot 录制前请先退出预览。", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭预览。", flush=True)
    finally:
        stop.set()
        server.server_close()
        for worker in workers:
            worker.join(timeout=2)
        if any(worker.is_alive() for worker in workers):
            print("部分相机读取尚未返回；如下次提示占用，请确认此程序已退出。", flush=True)


if __name__ == "__main__":
    main()
