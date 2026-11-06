"""不连接相机/机械臂的参数和反馈转发测试。"""
import unittest
import teleop_web as app


class Tests(unittest.TestCase):
    def test_disables_viewer_preserves_motion_parameters(self):
        args = ["--robot.port=/dev/ttyACM0", "--robot.max_relative_target=5",
                "--fps=15", "--display_data=true"]
        self.assertEqual(app.prepare_cli(args), args[:-1] + ["--display_data=false"])

    def test_handles_separate_display_argument(self):
        self.assertEqual(app.prepare_cli(["--display_data", "true", "--fps=15"]),
                         ["--fps=15", "--display_data=false"])

    def test_adds_false_when_not_supplied(self):
        self.assertEqual(app.prepare_cli(["--robot.cameras={}"]),
                         ["--robot.cameras={}", "--display_data=false"])

    def test_one_original_observation_read_preserves_identity(self):
        observation = {"elbow_flex.pos": 12.3, "wrist": object()}
        calls, published = [], []
        device = object()
        def original(self, *args, **kwargs):
            calls.append((self, args, kwargs))
            return observation
        wrapped = app.observation_wrapper(original, published.append)
        self.assertIs(wrapped(device), observation)
        self.assertEqual(calls, [(device, (), {})])
        self.assertEqual(published, [observation])

    def test_display_failure_does_not_replace_observation(self):
        observation = {"elbow_flex.pos": 12.3}
        def fail(_):
            raise RuntimeError("fake display failure")
        wrapped = app.observation_wrapper(lambda _: observation, fail)
        with self.assertLogs(app.__name__, level="ERROR"):
            self.assertIs(wrapped(object()), observation)

    def test_robot_read_failure_not_swallowed(self):
        def original(_):
            raise RuntimeError("fake bus error")
        wrapped = app.observation_wrapper(original, lambda _: None)
        with self.assertRaisesRegex(RuntimeError, "bus error"):
            wrapped(object())


if __name__ == "__main__":
    unittest.main(verbosity=2)
