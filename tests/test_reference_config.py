import tempfile
import unittest
from pathlib import Path

from bot_ia.config.loader import load_runtime_config


class ReferenceConfigTests(unittest.TestCase):
    def test_novel_reference_metadata_is_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "runtime.toml"
            config.write_text(
                '[providers.test]\nmodel="local"\n'
                '[universes.one_neko_punch]\n'
                'display_name="One Neko Punch"\n'
                'root_path="env:TEST_MISSING_ROOT"\n'
                'reference_universe_id="one_punch_man"\n'
                'reference_display_name="One-Punch Man"\n',
                encoding="utf-8",
            )
            loaded = load_runtime_config(config)
            universe = loaded.universe("one_neko_punch")
            self.assertEqual("one_punch_man", universe.reference_universe_id)
            self.assertEqual("One-Punch Man", universe.reference_display_name)


if __name__ == "__main__":
    unittest.main()
