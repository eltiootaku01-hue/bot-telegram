# -*- coding: utf-8 -*-
from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from bot_ia.core.web_queue import (
    SOFT_RESET_AFTER_INTERACTIONS,
    SelectorResolver,
    WebQueueManager,
)


class FakeElement:
    def __init__(
        self,
        *,
        visible=True,
        text="respuesta",
    ):
        self.visible = visible
        self.text = text
        self.filled = ""
        self.clicked = False

    async def is_visible(self):
        return self.visible

    async def fill(self, value):
        self.filled = value

    async def click(self):
        self.clicked = True

    async def inner_text(self):
        return self.text


class FakeLocatorCollection:
    def __init__(self, elements):
        self.elements = list(elements)
        self.filter_calls = []

    def filter(self, **kwargs):
        self.filter_calls.append(kwargs)
        return self

    async def count(self):
        return len(self.elements)

    def nth(self, index):
        return self.elements[index]


class FakePage:
    def __init__(self, locator_map):
        self.locator_map = locator_map
        self.waits = []
        self.reload_count = 0
        self.goto_calls = []

    def locator(self, selector):
        if selector == "[hidden]":
            return FakeLocatorCollection([])
        return self.locator_map[selector]

    async def wait_for_timeout(self, milliseconds):
        self.waits.append(milliseconds)

    async def reload(self, **kwargs):
        self.reload_count += 1

    async def goto(self, url, **kwargs):
        self.goto_calls.append((url, kwargs))


class FakeResource:
    def __init__(self):
        self.closed = 0

    async def close(self):
        self.closed += 1


class FakeBrowser(FakeResource):
    def is_connected(self):
        return True


class FakePlaywright(FakeResource):
    pass


class WebQueueCoreTests(unittest.IsolatedAsyncioTestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_selector_resolver_builds_css_or(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "selectors.json"
            path.write_text(
                json.dumps(
                    {
                        "gemini_web": {
                            "prompt_textarea": ["a", "b", "c"],
                        }
                    }
                ),
                encoding="utf-8",
            )

            resolver = SelectorResolver(path)
            self.assertEqual("a, b, c", resolver.get("prompt_textarea"))

    def test_lightweight_chromium_args_include_headless_mode(self):
        with patch.dict(
            os.environ,
            {"PLAYWRIGHT_DISABLE_IMAGES": "true"},
            clear=False,
        ):
            from bot_ia.core.web_queue import _lightweight_browser_args

            args = _lightweight_browser_args(headless=True)

        self.assertIn("--headless=new", args)
        for flag in (
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-sandbox",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-client-side-phishing-detection",
            "--disable-default-apps",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-sync",
            "--disable-translate",
            "--metrics-recording-only",
            "--no-zygote",
        ):
            self.assertIn(flag, args)
        self.assertIn("--blink-settings=imagesEnabled=false", args)

    async def test_get_active_locator_skips_hidden_and_uses_visible(self):
        manager = WebQueueManager(
            self.ROOT / "src" / "config" / "selectors.json"
        )
        hidden = FakeElement(visible=False)
        visible = FakeElement(visible=True)

        selector = manager.selectors.get("prompt_textarea")
        page = FakePage(
            {
                selector: FakeLocatorCollection([hidden, visible]),
            }
        )

        result = await manager.get_active_locator(
            page,
            "prompt_textarea",
            timeout_ms=0,
        )
        self.assertIs(result, visible)

    async def test_process_task_and_automatic_soft_reset(self):
        manager = WebQueueManager(
            self.ROOT / "src" / "config" / "selectors.json"
        )
        manager.interaction_counters["cari"] = (
            SOFT_RESET_AFTER_INTERACTIONS - 1
        )

        prompt_selector = manager.selectors.get("prompt_textarea")
        send_selector = manager.selectors.get("send_button")
        response_selector = manager.selectors.get("response_bubble")

        textarea = FakeElement()
        send_button = FakeElement()
        response = FakeElement(text="Hola desde Gemini")

        page = FakePage(
            {
                prompt_selector: FakeLocatorCollection([textarea]),
                send_selector: FakeLocatorCollection([send_button]),
                response_selector: FakeLocatorCollection([response]),
            }
        )
        manager.pages["cari"] = page

        result = await manager.process_task(
            "cari",
            {"prompt": "Hola"},
        )

        self.assertEqual("Hola desde Gemini", result)
        self.assertEqual("Hola", textarea.filled)
        self.assertTrue(send_button.clicked)
        self.assertEqual(1, page.reload_count)
        self.assertEqual(0, manager.interaction_counters["cari"])

    async def test_process_task_rejects_empty_prompt(self):
        manager = WebQueueManager(
            self.ROOT / "src" / "config" / "selectors.json"
        )
        manager.pages["cari"] = FakePage({})

        with self.assertRaises(ValueError):
            await manager.process_task(
                "cari",
                {"prompt": "   "},
            )

    async def test_soft_reset_uses_goto_after_reload_failure(self):
        manager = WebQueueManager(
            self.ROOT / "src" / "config" / "selectors.json"
        )

        class BrokenReloadPage(FakePage):
            async def reload(self, **kwargs):
                raise RuntimeError("reload failed")

        page = BrokenReloadPage({})
        manager.pages["cari"] = page
        manager.interaction_counters["cari"] = 12

        await manager.soft_reset_page("cari")

        self.assertEqual(1, len(page.goto_calls))
        self.assertEqual(0, manager.interaction_counters["cari"])

    async def test_graceful_shutdown_is_idempotent_and_cleans_references(self):
        manager = WebQueueManager(
            self.ROOT / "src" / "config" / "selectors.json"
        )
        context = FakeResource()
        browser = FakeBrowser()
        playwright = FakePlaywright()

        manager.context = context
        manager.browser = browser
        manager.playwright = playwright
        manager.pages["cari"] = FakePage({})
        manager.interaction_counters["cari"] = 7

        await manager.close_browser_pool()
        await manager.close_browser_pool()

        self.assertEqual(1, context.closed)
        self.assertEqual(1, browser.closed)
        self.assertEqual(1, playwright.closed)
        self.assertEqual({}, manager.pages)
        self.assertEqual({}, manager.interaction_counters)
        self.assertIsNone(manager.context)
        self.assertIsNone(manager.browser)
        self.assertIsNone(manager.playwright)


if __name__ == "__main__":
    unittest.main()
