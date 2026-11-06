"""Linux launcher regression tests using fake commands, without robot access."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Requires POSIX bash")
class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".launcher_test_", dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        commands = self.root / "commands"
        commands.mkdir()
        reader = commands / "readlink"
        reader.write_text('#!/bin/sh\n[ "$1" = "-e" ] && [ "$2" = "--" ] || exit 9\n'
                          'if [ "$MOCK_READLINK_EXIT" != "0" ]; then exit 1; fi\n'
                          'printf "%s\\n" "$MOCK_PORT"\n')
        reader.chmod(0o755)
        interpreter = self.root / "miniforge3/envs/so101_voice/bin/python"
        interpreter.parent.mkdir(parents=True)
        interpreter.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CAPTURE_FILE"\n')
        interpreter.chmod(0o755)
        self.capture = self.root / "args.txt"
        self.env = dict(os.environ, HOME=str(self.root),
                        PATH=str(commands) + os.pathsep + os.environ.get("PATH", ""),
                        MOCK_READLINK_EXIT="0", MOCK_PORT="/dev/ttyACM7",
                        CAPTURE_FILE=str(self.capture),
                        SO101_FOLLOWER_BY_ID="/dev/serial/by-id/follower-test",
                        SO101_TASK1_DATASET="/data/task1", SO101_TASK1_POSE="/pose/task1.json",
                        SO101_TASK2_DATASET="/data/task2", SO101_TASK2_POSE="/pose/task2.json",
                        SO101_TASK3_DATASET="/data/task3", SO101_TASK3_POSE="/pose/task3.json")
        self.launcher = Path(__file__).parent / "start_voice_tasks_v3.sh"

    def test_resolves_port_and_forwards_check_only(self):
        result = subprocess.run(["bash", str(self.launcher), "--check-config"],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.capture.read_text().splitlines()
        self.assertEqual(args[args.index("--port") + 1], "/dev/ttyACM7")
        self.assertIn("--check-config", args)
        self.assertNotIn("--execute", args)
        self.assertNotIn("/dev/serial/by-id/follower-test", args)

    def test_missing_link_never_launches_or_falls_back(self):
        self.env["MOCK_READLINK_EXIT"] = "1"
        result = subprocess.run(["bash", str(self.launcher), "--execute"],
                                env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Follower USB board not found", result.stderr)
        self.assertFalse(self.capture.exists())

    def test_no_execute_is_injected(self):
        result = subprocess.run(["bash", str(self.launcher)], env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--execute", self.capture.read_text().splitlines())


if __name__ == "__main__":
    unittest.main()
