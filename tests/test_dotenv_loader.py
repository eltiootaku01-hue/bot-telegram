import os
from pathlib import Path
import tempfile
import unittest

from bot_ia.config.dotenv import load_dotenv


class DotenvLoaderTests(unittest.TestCase):
    def test_loads_local_values_without_overwriting_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".env"
            path.write_text(
                "NEW_BOT_IA_VALUE='hello world'\nEXISTING_BOT_IA_VALUE=file\n",
                encoding="utf-8",
            )
            previous = os.environ.get("EXISTING_BOT_IA_VALUE")
            os.environ["EXISTING_BOT_IA_VALUE"] = "process"
            os.environ.pop("NEW_BOT_IA_VALUE", None)
            try:
                load_dotenv(path)
                self.assertEqual("hello world", os.environ["NEW_BOT_IA_VALUE"])
                self.assertEqual("process", os.environ["EXISTING_BOT_IA_VALUE"])
            finally:
                os.environ.pop("NEW_BOT_IA_VALUE", None)
                if previous is None:
                    os.environ.pop("EXISTING_BOT_IA_VALUE", None)
                else:
                    os.environ["EXISTING_BOT_IA_VALUE"] = previous


if __name__ == "__main__":
    unittest.main()
