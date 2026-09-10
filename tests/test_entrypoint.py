import os
from pathlib import Path
import subprocess
import sys
import unittest


class EntrypointTests(unittest.TestCase):
    def test_module_help_starts_without_runtime_configuration(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        result = subprocess.run(
            [sys.executable, "-m", "bot_ia", "--help"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("BOT-IA Knowledge Engine", result.stdout)
        self.assertIn("--mode", result.stdout)


if __name__ == "__main__":
    unittest.main()
