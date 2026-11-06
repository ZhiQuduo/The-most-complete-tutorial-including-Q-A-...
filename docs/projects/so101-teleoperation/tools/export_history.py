"""导出本窗口及明确继承的父窗口可见消息；不导出系统/开发者指令、推理或工具载荷。"""
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DEST = BASE / "evidence" / "2026-10-29"
SOURCES = [
    ("inherited-parent", Path(r"C:\Users\Lenovo\.codex\sessions\2026\10\12\rollout-2026-10-12T09-53-50-01a12dd0-f377-7de2-9266-255836ab4907.jsonl")),
    ("current-window", Path(r"C:\Users\Lenovo\.codex\sessions\2026\10\15\rollout-2026-10-15T12-12-56-01a13dc3-5d6d-7330-8b22-19a6d68c446a.jsonl")),
]
DEST.mkdir(parents=True, exist_ok=True)
messages, stats = [], []
for label, source in SOURCES:
    raw = source.read_bytes()
    counts = Counter()
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        entry = json.loads(line)
        payload = entry.get("payload", {})
        if entry.get("type") != "response_item" or payload.get("type") != "message":
            continue
        role = payload.get("role")
        if role not in ("user", "assistant"):
            continue
        if role == "assistant" and payload.get("channel") not in (None, "final", "commentary"):
            continue
        parts = payload.get("content", [])
        text = "\n".join(p.get("text", "") for p in parts if p.get("type") in ("text", "input_text", "output_text"))
        if text.startswith(("<environment_context>", "<external_codex_apps_open_page>")):
            continue
        if role == "user" and "查询这个窗口里面全部的历史，维护项目文档" in text:
            break
        if not text.strip():
            continue
        text = re.sub(r"<oai-mem-citation>.*?</oai-mem-citation>", "", text, flags=re.S)
        assets = []
        for file_name in dict.fromkeys(re.findall(r"codex-clipboard-[\w-]+\.png", text)):
            original = Path(r"C:\Users\Lenovo\AppData\Local\Temp") / file_name
            if original.is_file():
                target = DEST / "assets" / file_name
                target.parent.mkdir(exist_ok=True)
                if not target.exists():
                    shutil.copy2(original, target)
                assets.append("assets/" + file_name)
        counts[role] += 1
        messages.append(dict(source=label, source_line=number, timestamp=entry.get("timestamp"),
                             role=role, text=text, images=assets))
    stats.append(dict(label=label, path=str(source), scanned_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                      exported_counts=dict(counts), cutoff="first matching documentation-maintenance request"))
body = ["# 本窗口与继承父窗口的可见消息存档", "",
        "仅导出 user/assistant 可见文本和仍存在的用户附件；排除 system/developer、内部推理、工具载荷和本次文档维护过程。",
        "原始截图未做 OCR 重解释；用户消息时间来自会话记录 UTC，不是截图里可能漂移的虚拟机时钟。", ""]
for i, message in enumerate(messages, 1):
    body += [f"## E{i:03d} | {message['source']}:{message['source_line']} | {message['role']} | {message['timestamp']}", "", message["text"], ""]
    body.extend(f"[保留的原截图]({image})\n" for image in message["images"])
(DEST / "conversation.md").write_text("\n".join(body), encoding="utf-8")
(DEST / "history-index.json").write_text(json.dumps(dict(sources=stats, messages=messages), ensure_ascii=False, indent=2), encoding="utf-8")
inventory = []
for folder in ("无相机Demo", "双相机Demo", "语音任务助手"):
    for file in sorted((Path(r"D:\具身智能") / folder).glob("*")):
        if file.is_file() and file.suffix in (".py", ".md", ".bak"):
            data = file.read_bytes()
            inventory.append(dict(path=str(file), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
(DEST / "artifact-inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(dict(sources=stats, messages=len(messages), retained_images=len(list((DEST / "assets").glob("*.png")))), ensure_ascii=False, indent=2))
