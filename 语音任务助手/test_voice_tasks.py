"""模拟任务管理与配置绑定，不访问音频、串口或机械臂。"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import voice_tasks as voice


class VoiceTasksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".voice_test_", dir=Path(__file__).resolve().parent)
        assert Path(self.temp.name).resolve().is_relative_to(Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        data = root / "so101_pick_place_02"
        (data / "meta").mkdir(parents=True)
        (data / "meta/info.json").write_text("{}")
        for name in ("robot_python", "so101_home.py", "port"):
            (root / name).touch()
        self.profile = {"dataset": {"root": str(data), "repo_id": "local/so101_pick_place_02", "episode": 0},
                        "robot_id": "follower_arm", "use_degrees": True}
        self.pose = root / "pick_place_02_start.json"
        self.pose.write_text(json.dumps(self.profile))
        self.args = SimpleNamespace(robot_python=root / "robot_python", helper=root / "so101_home.py",
                                    pose=self.pose, dataset=data, port=str(root / "port"), execute=True)

    def test_only_whole_commands_match(self):
        self.assertEqual(voice.intent("执行 任务 1。"), "start")
        self.assertIsNone(voice.intent("不要执行任务一"))
        self.assertEqual(voice.intent("执行任务二"), "start2")
        self.assertEqual(voice.intent("完成 任务 2。"), "start2")
        self.assertIsNone(voice.intent("不要执行任务二"))
        self.assertEqual(voice.intent("执行任务三"), "start3")
        self.assertEqual(voice.intent("请 完成 任务 3。"), "start3")
        self.assertEqual(voice.intent("完成任务三"), "start3")
        self.assertIsNone(voice.intent("不要执行任务三"))
        self.assertIsNone(voice.intent("不要请完成任务三"))
        self.assertIsNone(voice.intent("请完成任务三然后再执行任务一"))

    def test_rejects_mismatched_pose(self):
        self.profile["dataset"]["root"] = str(self.args.dataset.parent / "so101_pick_place_01")
        self.pose.write_text(json.dumps(self.profile))
        with self.assertRaises(ValueError):
            voice.validate(self.args)

    def test_rejects_missing_dataset(self):
        (self.args.dataset / "meta/info.json").unlink()
        with self.assertRaises(ValueError):
            voice.validate(self.args)

    @patch.object(voice.subprocess, "Popen")
    def test_dry_run_cannot_start_process(self, popen):
        self.args.execute = False
        voice.Runner(self.args).start()
        popen.assert_not_called()

    @patch.object(voice.subprocess, "Popen")
    def test_busy_drops_duplicate_without_queue(self, popen):
        runner = voice.Runner(self.args)
        popen.return_value.poll.return_value = None
        runner.start()
        runner.start()
        self.assertEqual(popen.call_count, 1)
        argv = popen.call_args.args[0]
        self.assertIn(str(self.pose), argv)
        self.assertIn("--execute", argv)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    @patch.object(voice.os, "killpg", create=True)
    def test_stop_signals_group_and_locks(self, killpg):
        runner = voice.Runner(self.args)
        runner.child = Mock(pid=123)
        runner.stop()
        killpg.assert_called_once_with(123, voice.signal.SIGINT)
        self.assertTrue(runner.blocked)
        self.assertTrue(runner.stopping)

    @patch.object(voice.subprocess, "Popen")
    def test_failed_task_locks_future_starts(self, popen):
        runner = voice.Runner(self.args)
        runner.child = Mock(returncode=1)
        runner.child.poll.return_value = 1
        self.assertTrue(runner.poll())
        runner.start()
        popen.assert_not_called()
        self.assertTrue(runner.blocked)

    @patch.object(voice.time, "monotonic", return_value=100)
    @patch.object(voice.subprocess, "Popen")
    def test_success_has_cooldown_and_no_auto_repeat(self, popen, clock):
        runner = voice.Runner(self.args)
        runner.child = Mock(returncode=0)
        runner.child.poll.return_value = 0
        runner.poll()
        self.assertFalse(runner.blocked)
        self.assertIsNone(runner.child)
        self.assertEqual(runner.ready_after, 103)
        runner.start()
        popen.assert_not_called()

    def add_second(self):
        data = self.args.dataset.parent / "so101_pick_place_03"
        (data / "meta").mkdir(parents=True)
        (data / "meta/info.json").write_text("{}")
        profile = {**self.profile, "dataset": {"root": str(data), "repo_id": "local/so101_pick_place_03", "episode": 0}}
        pose = data.parent / "pick_place_03_start.json"
        pose.write_text(json.dumps(profile))
        self.args.dataset2, self.args.pose2 = data, pose

    @patch.object(voice.subprocess, "Popen")
    def test_task_two_uses_third_pose_once(self, popen):
        self.add_second()
        runner = voice.Runner(self.args)
        runner.start(2)
        runner.start(2)
        popen.assert_called_once()
        argv = popen.call_args.args[0]
        self.assertIn(str(self.args.pose2), argv)
        self.assertNotIn(str(self.args.pose), argv)
        self.assertEqual(argv.count("demo"), 1)
        self.assertEqual(runner.active_task, 2)

    @patch.object(voice.subprocess, "Popen")
    def test_busy_task_one_rejects_task_two(self, popen):
        self.add_second()
        runner = voice.Runner(self.args)
        runner.start()
        runner.start(2)
        popen.assert_called_once()
        self.assertEqual(runner.active_task, 1)

    @patch.object(voice.subprocess, "Popen")
    def test_task_two_wrong_pose_never_falls_back_to_one(self, popen):
        self.add_second()
        self.args.pose2 = self.args.pose
        voice.Runner(self.args).start(2)
        popen.assert_not_called()

    @patch.object(voice.subprocess, "Popen")
    def test_task_two_unconfigured_does_not_start_one(self, popen):
        voice.Runner(self.args).start(2)
        popen.assert_not_called()

    def add_third(self):
        data = self.args.dataset.parent / "so101_task3_test"
        (data / "meta").mkdir(parents=True)
        (data / "meta/info.json").write_text("{}")
        profile = {**self.profile, "dataset": {"root": str(data), "repo_id": "local/so101_task3_test", "episode": 0}}
        pose = data.parent / "so101_task3_test_start.json"
        pose.write_text(json.dumps(profile))
        self.args.dataset3, self.args.pose3 = data, pose

    @patch.object(voice.subprocess, "Popen")
    def test_task_three_starts_once_with_only_its_pose(self, popen):
        self.add_second()
        self.add_third()
        runner = voice.Runner(self.args)
        runner.start(3)
        runner.start(3)
        popen.assert_called_once()
        argv = popen.call_args.args[0]
        self.assertIn(str(self.args.pose3), argv)
        self.assertNotIn(str(self.args.pose2), argv)
        self.assertNotIn(str(self.args.pose), argv)
        self.assertEqual(argv.count("demo"), 1)
        self.assertEqual(runner.active_task, 3)

    @patch.object(voice.subprocess, "Popen")
    def test_task_three_missing_binding_never_falls_back(self, popen):
        voice.Runner(self.args).start(3)
        popen.assert_not_called()

    @patch.object(voice.subprocess, "Popen")
    def test_task_three_wrong_pose_never_falls_back(self, popen):
        self.add_third()
        self.args.pose3 = self.pose
        voice.Runner(self.args).start(3)
        popen.assert_not_called()

    @patch.object(voice.subprocess, "Popen")
    def test_busy_task_one_rejects_three(self, popen):
        self.add_third()
        runner = voice.Runner(self.args)
        runner.start()
        runner.start(3)
        popen.assert_called_once()
        self.assertEqual(runner.active_task, 1)

    @patch.object(voice.subprocess, "Popen")
    def test_task_three_dry_run_has_no_child(self, popen):
        self.add_third()
        self.args.execute = False
        voice.Runner(self.args).start(3)
        popen.assert_not_called()

    @patch.object(voice.subprocess, "Popen")
    def test_failed_three_blocks_all_tasks(self, popen):
        self.add_third()
        runner = voice.Runner(self.args)
        runner.active_task = 3
        runner.child = Mock(returncode=1)
        runner.child.poll.return_value = 1
        runner.poll()
        runner.start(3)
        runner.start(1)
        popen.assert_not_called()
        self.assertTrue(runner.blocked)

    @patch.object(voice.os, "killpg", create=True)
    def test_task_three_stop_signals_its_group_and_locks(self, killpg):
        self.add_third()
        runner = voice.Runner(self.args)
        runner.active_task = 3
        runner.child = Mock(pid=321)
        runner.stop()
        killpg.assert_called_once_with(321, voice.signal.SIGINT)
        self.assertTrue(runner.blocked)

    @patch.object(voice.subprocess, "Popen")
    def test_task_three_missing_dataset_does_not_spawn(self, popen):
        self.add_third()
        (self.args.dataset3 / "meta/info.json").unlink()
        voice.Runner(self.args).start(3)
        popen.assert_not_called()


if __name__ == "__main__":
    with contextlib.redirect_stdout(io.StringIO()):
        unittest.main()
