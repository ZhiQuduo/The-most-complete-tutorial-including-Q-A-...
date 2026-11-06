"""纯软件验证，不导入真实 LeRobot、不访问串口、不发送硬件命令。"""
import contextlib
import io
import json
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import so101_home as app


def calibration():
    return {n: dict(id=i, drive_mode=0, homing_offset=0, range_min=0, range_max=4095)
            for i, n in enumerate(app.JOINTS, 1)}


def pose(value=0):
    return {n: float(value) for n in app.JOINTS}


class Clock:
    def __init__(self, delayed=False):
        self.now = 0.0
        self.delayed = delayed

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(0.00001, seconds)
        if self.delayed:
            self.now += 1.0
            self.delayed = False


class MotionDevice:
    def __init__(self, clock, stuck=False, bad_health=False):
        self.cal = calibration()
        self.current = pose()
        self.clock = clock
        self.stuck = stuck
        self.bad_health = bad_health
        self.goals = []
        self.primed = False
        self.health_reads = 0

    def positions(self):
        return dict(self.current)

    def prime_and_enable(self):
        self.primed = True
        return self.positions()

    def health(self, require_torque):
        self.health_reads += 1
        if self.bad_health and self.health_reads >= 3:
            raise RuntimeError("simulated torque/status fault")

    def goal(self, target):
        self.goals.append((self.clock(), dict(target)))
        if not self.stuck:
            self.current = dict(target)


class Bus:
    last = None

    def __init__(self, **kwargs):
        Bus.last = self
        self.cal = kwargs["calibration"]
        self.raw = {n: 2048 for n in app.JOINTS}
        self.register_goal = {n: 4090 for n in app.JOINTS}
        self.is_connected = False
        self.calls = []

    def connect(self, **kwargs):
        self.is_connected = True

    def set_baudrate(self, rate):
        pass

    def ping(self, index):
        return 777

    def read_calibration(self):
        return self.cal

    def sync_read(self, field, **kwargs):
        if field == "Present_Position":
            return dict(self.raw)
        if field == "Goal_Position":
            return dict(self.register_goal)
        return {n: 0 for n in app.JOINTS}

    def sync_write(self, field, values, **kwargs):
        self.calls.append((field, dict(values)))
        if field == "Goal_Position":
            self.register_goal = dict(values)

    def enable_torque(self, **kwargs):
        self.calls.append(("enable_torque", None))

    def disconnect(self, disable_torque):
        self.calls.append(("disconnect", disable_torque))
        self.is_connected = False


@contextlib.contextmanager
def fake_modules():
    motors = types.ModuleType("lerobot.motors")
    motors.Motor = lambda *args: args
    motors.MotorCalibration = lambda **kwargs: types.SimpleNamespace(**kwargs)
    motors.MotorNormMode = types.SimpleNamespace(DEGREES=1, RANGE_0_100=2)
    feetech = types.ModuleType("lerobot.motors.feetech")
    feetech.FeetechMotorsBus = Bus
    ports = types.ModuleType("serial.tools.list_ports")
    ports.comports = lambda: [types.SimpleNamespace(device="TEST", serial_number="FOLLOWER-TEST")]
    modules = {"lerobot": types.ModuleType("lerobot"), "lerobot.motors": motors,
               "lerobot.motors.feetech": feetech, "serial": types.ModuleType("serial"),
               "serial.tools": types.ModuleType("serial.tools"), "serial.tools.list_ports": ports}
    with patch.dict(sys.modules, modules):
        yield


class Tests(unittest.TestCase):
    def setUp(self):
        workspace = Path(__file__).resolve().parent
        self.tmp = tempfile.TemporaryDirectory(dir=workspace, prefix="_test_")
        # 清理只允许发生在本测试文件所在目录内。
        self.assertTrue(Path(self.tmp.name).resolve().is_relative_to(workspace))
        self.addCleanup(self.tmp.cleanup)
        self.cal_file = Path(self.tmp.name) / "calibration.json"
        self.cal_file.write_text(json.dumps(calibration()), encoding="utf-8")
        self.silence = contextlib.redirect_stdout(io.StringIO())
        self.silence.__enter__()
        self.addCleanup(self.silence.__exit__, None, None, None)

    def test_degrees_and_gripper_percent_roundtrip(self):
        desired = pose(25)
        actual = app.from_raw(app.to_raw(desired, calibration()), calibration())
        for n in app.JOINTS:
            self.assertLess(abs(actual[n]-desired[n]), 0.09)
        self.assertEqual(app.to_raw(pose(), calibration())["gripper"], 0)

    def test_reject_nan_infinity_missing_and_outside_range(self):
        for value in (math.nan, math.inf, -math.inf, 181):
            target = pose()
            target["elbow_flex"] = value
            with self.assertRaises(ValueError):
                app.validate_pose(target, calibration())
        with self.assertRaises(ValueError):
            app.finite_pose({"gripper": 0})

    def test_reject_raw_feedback_outside_range(self):
        raw = {n: 2048 for n in app.JOINTS}
        raw["gripper"] = 4096
        with self.assertRaises(ValueError):
            app.from_raw(raw, calibration())

    def test_readonly_open_close_no_motor_writes(self):
        with fake_modules():
            with app.Device("TEST", self.cal_file) as device:
                device.positions()
            self.assertEqual(Bus.last.calls, [("disconnect", False)])

    def test_wrong_usb_rejected_before_bus_created(self):
        Bus.last = None
        with fake_modules(), self.assertRaises(RuntimeError):
            with app.Device("TEST", self.cal_file, "LEADER-OTHER"):
                pass
        self.assertIsNone(Bus.last)

    def test_calibration_mismatch_rejected_without_writes(self):
        original = Bus.read_calibration
        def changed(bus):
            result = dict(original(bus))
            result["elbow_flex"] = types.SimpleNamespace(**{**calibration()["elbow_flex"], "homing_offset": 5})
            return result
        with fake_modules(), patch.object(Bus, "read_calibration", changed), self.assertRaises(RuntimeError):
            with app.Device("TEST", self.cal_file):
                pass
        self.assertEqual(Bus.last.calls, [("disconnect", False)])

    def test_current_goal_written_verified_before_torque(self):
        with fake_modules(), patch.object(app.Device, "health"):
            with app.Device("TEST", self.cal_file) as device:
                device.prime_and_enable()
                calls = Bus.last.calls
                self.assertEqual(calls[0], ("Goal_Position", Bus.last.raw))
                self.assertEqual(calls[1][0], "enable_torque")

    def test_exception_freezes_and_does_not_drop_arm(self):
        with fake_modules(), self.assertRaisesRegex(RuntimeError, "stop"):
            with app.Device("TEST", self.cal_file) as device:
                device.goal(pose(10))
                raise RuntimeError("stop")
        self.assertEqual(Bus.last.calls[-2], ("Goal_Position", Bus.last.raw))
        self.assertEqual(Bus.last.calls[-1], ("disconnect", False))

    def test_motion_finishes_with_rate_limit_and_settling(self):
        clock = Clock()
        device = MotionDevice(clock)
        target = pose(15)
        target["gripper"] = 30
        app.home_motion(device, target, clock, clock.sleep)
        self.assertTrue(device.primed)
        self.assertEqual(device.current, target)
        self.assertGreaterEqual(clock(), app.move_duration(pose(), target) + 0.49)
        for (t0, p0), (t1, p1) in zip(device.goals, device.goals[1:]):
            for n in app.JOINTS:
                self.assertLessEqual(abs(p1[n]-p0[n]), app.SPEED[n]*max(0, t1-t0)+1e-7)

    def test_scheduler_delay_does_not_generate_catchup_step(self):
        clock = Clock(delayed=True)
        device = MotionDevice(clock)
        app.home_motion(device, pose(15), clock, clock.sleep)
        for (_, p0), (_, p1) in zip(device.goals, device.goals[1:]):
            for n in app.JOINTS:
                self.assertLessEqual(abs(p1[n]-p0[n]), app.SPEED[n]/30+1e-7)

    def test_stall_aborts_instead_of_increasing_goal(self):
        clock = Clock()
        device = MotionDevice(clock, stuck=True)
        with self.assertRaisesRegex(RuntimeError, "跟不上") as caught:
            app.home_motion(device, pose(30), clock, clock.sleep)
        for field in ("超差详情", "current", "goal", "error", "threshold"):
            self.assertIn(field, str(caught.exception))
        self.assertLess(clock(), 20)
        self.assertLessEqual(max(abs(p["elbow_flex"]) for _, p in device.goals), 2.00001)

    def test_health_fault_aborts(self):
        clock = Clock()
        device = MotionDevice(clock, bad_health=True)
        with self.assertRaisesRegex(RuntimeError, "fault"):
            app.home_motion(device, pose(30), clock, clock.sleep)

    def test_large_travel_rejected_before_enable(self):
        clock = Clock()
        device = MotionDevice(clock)
        target = pose()
        target["shoulder_pan"] = 100
        with self.assertRaisesRegex(ValueError, "90"):
            app.home_motion(device, target, clock, clock.sleep)
        self.assertFalse(device.primed)
        self.assertFalse(device.goals)

    def test_changed_calibration_invalidates_saved_home(self):
        profile = dict(schema=1, robot_id="follower_arm", use_degrees=True, positions=pose(),
                       usb_serial="FOLLOWER-TEST", calibration_file=str(self.cal_file),
                       calibration_sha256=app.digest(self.cal_file))
        path = Path(self.tmp.name) / "pose.json"
        path.write_text(json.dumps(profile))
        app.load_profile(path)
        self.cal_file.write_text(self.cal_file.read_text()+"\n")
        with self.assertRaisesRegex(ValueError, "校准文件"):
            app.load_profile(path)

    def test_save_never_overwrites_existing_pose(self):
        path = Path(self.tmp.name) / "pose.json"
        path.write_text("keep me")
        with self.assertRaises(FileExistsError):
            app.save_profile(types.SimpleNamespace(pose=path))
        self.assertEqual(path.read_text(), "keep me")

    def test_cycle_binds_dataset_and_preserves_torque(self):
        root = Path(self.tmp.name) / "recording"
        (root / "meta").mkdir(parents=True)
        (root / "meta/info.json").write_text("{}")
        profile = {"calibration_file": str(self.cal_file), "dataset": {
            "root": str(root), "repo_id": "local/demo", "info_sha256": app.digest(root / "meta/info.json")}}
        command = app.replay_command(types.SimpleNamespace(port="TEST"), profile)
        self.assertIn("--robot.disable_torque_on_disconnect=false", command)
        self.assertIn("--robot.max_relative_target=5", command)
        self.assertNotIn("--robot.max_relative_target=2", command)
        self.assertIn("--dataset.repo_id=local/demo", command)


if __name__ == "__main__":
    unittest.main(verbosity=2)
