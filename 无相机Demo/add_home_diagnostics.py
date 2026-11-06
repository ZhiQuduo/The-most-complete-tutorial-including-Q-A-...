"""仅为 Ubuntu 现有归位脚本增加超差详情；不更改运动参数、不访问硬件。"""
from datetime import datetime
from pathlib import Path

path = Path.home() / "lerobot/so101_home.py"
text = path.read_text(encoding="utf-8")
old = 'raise RuntimeError("关节连续跟不上目标，可能受阻；已中止归位。")'
new = 'raise RuntimeError("关节连续跟不上目标，可能受阻；已中止归位。超差详情：" + str({n: {"current": round(current[n], 3), "goal": round(last_goal[n], 3), "error": round(last_goal[n] - current[n], 3), "threshold": LEAD[n] * 0.75} for n in JOINTS if abs(last_goal[n] - current[n]) > LEAD[n] * 0.75}))'
if "超差详情：" in text:
    print("已经有超差诊断，无需重复修改。")
elif text.count(old) != 1:
    raise SystemExit("没有找到唯一的原报错行，保留原文件，请核对当前脚本版本。")
else:
    updated = text.replace(old, new, 1)
    compile(updated, str(path), "exec")
    backup = path.with_name(path.name + ".bak_diag_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    with backup.open("x", encoding="utf-8") as stream:
        stream.write(text)
    path.write_text(updated, encoding="utf-8")
    print("已增加超差关节、反馈、目标和误差详情。备份：", backup)
    print("未修改速度、跟随阈值、超时时间、回放限幅、PID 或力矩参数。")
