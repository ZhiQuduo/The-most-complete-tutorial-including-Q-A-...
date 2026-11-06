#!/usr/bin/env python3
"""离线检查录制的请求与从臂反馈差值。不导入机器人、不访问串口。"""
import argparse
import json
import math
from pathlib import Path


def percentile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def inspect(root):
    import pyarrow.parquet as pq

    root = Path(root)
    info = json.loads((root / "meta/info.json").read_text(encoding="utf-8"))
    action_names = info["features"]["action"]["names"]
    state_names = info["features"]["observation.state"]["names"]
    if len(set(action_names)) != len(action_names) or len(set(state_names)) != len(state_names):
        raise ValueError("关节名称重复，无法对齐。")
    if set(action_names) != set(state_names):
        raise ValueError("动作和反馈的关节名称不一致。")
    errors = {name: [] for name in action_names}
    count = 0
    for path in sorted((root / "data").rglob("*.parquet")):
        for batch in pq.ParquetFile(path).iter_batches(
            columns=["episode_index", "action", "observation.state"], batch_size=512
        ):
            for row in batch.to_pylist():
                if row["episode_index"] != 0:
                    continue
                if len(row["action"]) != len(action_names) or len(row["observation.state"]) != len(state_names):
                    raise ValueError("数据维数与元信息不一致。")
                state = dict(zip(state_names, row["observation.state"]))
                for name, requested in zip(action_names, row["action"]):
                    delta = abs(float(requested) - float(state[name]))
                    if not math.isfinite(delta):
                        raise ValueError("轨迹含有非有限数值。")
                    errors[name].append(delta)
                count += 1
    if not count:
        raise ValueError("没有读到 episode 0。")
    print("文件目录:", root)
    print("段号: 0，帧数:", count, "，设定帧率:", info["fps"])
    print(f"{'关节':<20} {'平均差':>9} {'P95差':>9} {'最大差':>9} {'差>2占比':>11} {'差>5占比':>11}")
    for name in action_names:
        values = errors[name]
        print(f"{name:<20} {sum(values)/count:9.2f} {percentile(values, .95):9.2f} "
              f"{max(values):9.2f} {sum(v>2 for v in values)/count:10.1%} "
              f"{sum(v>5 for v in values)/count:10.1%}")
    print("前五轴单位为度；夹爪单位为校准范围百分点。")
    print("这些是录制时同一帧的请求与反馈差，不是本次回放误差，也不是末端厘米误差。")
    print("单帧差值含运动跟随/采样时序影响，不能单独证明机械故障或限幅就是根因。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path,
                        default=Path.home() / "lerobot/recordings/so101_pick_place_02")
    args = parser.parse_args()
    inspect(args.root)
