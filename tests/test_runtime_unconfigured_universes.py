from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bot_ia.config.models import RuntimeConfig, UniverseConfig
from bot_ia.runtime import _build_universe_runtime


class RuntimeUnconfiguredUniversesTests(unittest.TestCase):
    def test_declared_universe_without_folder_is_registered_with_no_entries(self) -> None:
        with TemporaryDirectory() as tmp:
            config = RuntimeConfig(
                providers=(),
                services=(),
                universes=(
                    UniverseConfig(
                        "neko_fish_online",
                        "Neko Fish Online",
                        Path(tmp) / "missing",
                        reference_universe_id="sword_art_online",
                        reference_display_name="Sword Art Online",
                    ),
                ),
            )
            registry, runtimes = _build_universe_runtime(config)

        self.assertEqual(tuple(u.universe_id for u in registry.all()), ("neko_fish_online",))
        self.assertEqual(tuple(u.definition.universe_id for u in runtimes), ("neko_fish_online",))
        self.assertEqual(runtimes[0].entries, ())
        self.assertEqual(runtimes[0].entity_index.for_universe("neko_fish_online"), ())


if __name__ == "__main__":
    unittest.main()
