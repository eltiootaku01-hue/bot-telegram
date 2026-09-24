# -*- coding: utf-8 -*-
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest


class CodePolicyTests(unittest.TestCase):
    def test_policy_script_passes_itself(self) -> None:
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "check_code_policy.py"
        completed = subprocess.run(
            [sys.executable, str(script), str(script.relative_to(root))],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_policy_detects_bom_bad_import_and_pass_only_exception(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.py"
            path.write_bytes(
                bytes.fromhex("efbbbf")
                + b"# -*- coding: utf-8 -*-\\n"
                + b"from PySide6.Core import QObject\\n"
                + b"try:\\n"
                + b"    pass\\n"
                + b"except Exception:\\n"
                + b"    pass\\n"
            )
            script = root / "scripts" / "check_code_policy.py"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    str(path),
                ],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, completed.returncode)
            self.assertIn("UTF-8 BOM is forbidden", completed.stdout)
            self.assertIn("forbidden import path", completed.stdout)
            self.assertIn("except Exception: pass", completed.stdout)


if __name__ == "__main__":
    unittest.main()
