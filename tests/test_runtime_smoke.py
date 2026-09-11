import os
from pathlib import Path
import unittest

from bot_ia.core.application import ApplicationRequest
from bot_ia.runtime import build_runtime


class RuntimeSmokeTests(unittest.TestCase):
    def test_desktop_core_can_answer_without_remote_api(self):
        root = Path(__file__).resolve().parents[1]
        previous = os.environ.get("BOT_IA_ONE_NEKO_PUNCH_ROOT")
        os.environ["BOT_IA_ONE_NEKO_PUNCH_ROOT"] = str(root / "biblioteca")
        runtime = build_runtime(root)
        try:
            application = runtime.build_application(default_universe_id="one_neko_punch", provider_id="openai")
            response = application.handle(ApplicationRequest("smoke-user", "smoke-session", "hola"))
            self.assertTrue(response.text.strip())
            self.assertIn("IA-chan", response.text)
            self.assertFalse(response.decision.external_api_authorized)
        finally:
            runtime.memory_store.close()
            if previous is None:
                os.environ.pop("BOT_IA_ONE_NEKO_PUNCH_ROOT", None)
            else:
                os.environ["BOT_IA_ONE_NEKO_PUNCH_ROOT"] = previous


if __name__ == "__main__":
    unittest.main()
