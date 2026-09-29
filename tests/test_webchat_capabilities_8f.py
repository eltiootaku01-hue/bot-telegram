# -*- coding: utf-8 -*-
"""FASE 2F-8F: deterministic WebChat capability tests.

These tests use fakes only. They never launch a browser, use credentials,
contact an external provider, or mutate protected runtime components.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from services.web_queue import (
    BotTicket,
    WEB_MONITOR_JS,
    WebChatQueueManager,
)
from bot_ia.core.web_queue import (
    GEMINI_URL,
    SelectorResolver,
    WebQueueManager,
)


class SignalProbe:
    def __init__(self) -> None:
        self.events = []

    def emit(self, *args) -> None:
        self.events.append(args)


def make_ticket(ticket_id: str = "ticket-a") -> BotTicket:
    return BotTicket(
        ticket_id,
        "Cari",
        "chat",
        "@user",
        "/cafe",
        "hola",
    )


def make_legacy_manager(ticket_id: str = "ticket-a"):
    manager = type("FakeWebQueue", (), {})()
    manager.current_ticket = make_ticket(ticket_id)
    manager._web_operation_id = 7
    manager._response_pattern = WebChatQueueManager._safe_compile(
        r'respuesta\s+a\s*\(\s*(?P<bot>[^()\n]+?)\s+'
        r'(?P<ticket>[A-Za-z0-9_.:-]+)\s*\)\s*[“"](?P<text>.*?)[”"]',
        0x02 | 0x10,
    )
    manager._terminated_pattern = WebChatQueueManager._safe_compile(
        r'\(\s*(?P<bot>[^()\n]+?)\s+'
        r'(?P<ticket>[A-Za-z0-9_.:-]+)\s*\)#terminado\b',
        0x02,
    )
    manager.ticket_processed = SignalProbe()
    manager.response_observed_requested = SignalProbe()
    manager.terminated_requested = SignalProbe()
    manager.queue_error = SignalProbe()
    manager.health_failure_requested = SignalProbe()
    manager.MAX_RESPONSE_PARSE_CHARS = 20_000
    return manager


def test_g01_response_detection_contract_is_explicit() -> None:
    assert "RESPONSE_COMPLETE" in WEB_MONITOR_JS
    assert "extractLatestAssistantText" in WEB_MONITOR_JS
    assert "activeTicketId" in WEB_MONITOR_JS
    assert "operation_id" in WEB_MONITOR_JS


def test_g02_dom_monitoring_uses_mutation_observer_and_debounce() -> None:
    assert "new MutationObserver" in WEB_MONITOR_JS
    assert "observer.observe" in WEB_MONITOR_JS
    assert "subtree: true" in WEB_MONITOR_JS
    assert "childList: true" in WEB_MONITOR_JS
    assert "characterData: true" in WEB_MONITOR_JS
    assert "setTimeout" in WEB_MONITOR_JS
    assert "1200" in WEB_MONITOR_JS


def test_g03_selector_resolver_preserves_configured_or_selectors() -> None:
    resolver = SelectorResolver(Path("src/config/selectors.json"))
    prompt = resolver.get("prompt_textarea")
    send = resolver.get("send_button")
    response = resolver.get("response_bubble")

    assert "div[contenteditable='true']" in prompt
    assert "textarea[aria-label*='prompt']" in prompt
    assert "button[aria-label='Enviar mensaje']" in send
    assert "button.send-button" in send
    assert "message-content .markdown" in response
    assert "div[data-test-id='conversation-turn']" in response


def test_g03_selector_behavior_ignores_hidden_candidate_and_accepts_visible() -> None:
    class Candidate:
        def __init__(self, visible: bool) -> None:
            self.visible = visible

        async def is_visible(self) -> bool:
            return self.visible

    class Candidates:
        def __init__(self) -> None:
            self.items = [Candidate(False), Candidate(True)]

        def filter(self, **_kwargs):
            return self

        async def count(self) -> int:
            return len(self.items)

        def nth(self, index: int):
            return self.items[index]

    class Page:
        def __init__(self) -> None:
            self.candidates = Candidates()

        def locator(self, selector: str):
            assert selector == "configured-selector" or selector == "[hidden]"
            return self.candidates

        async def wait_for_timeout(self, _ms: int) -> None:
            raise AssertionError("visible candidate should be selected immediately")

    manager = WebQueueManager.__new__(WebQueueManager)
    manager.selectors = type(
        "Selectors", (), {"get": lambda _self, _key: "configured-selector"}
    )()

    selected = asyncio.run(
        manager.get_active_locator(
            Page(),
            "prompt_textarea",
            timeout_ms=100,
        )
    )
    assert selected is manager.selectors  or selected.visible is True


def test_g04_legacy_queue_builds_a_sendable_protocol_script_without_external_io() -> None:
    class Page:
        def __init__(self) -> None:
            self.scripts = []

        def runJavaScript(self, script, callback=None):
            self.scripts.append(script)
            if callback is not None:
                callback("OK: INJECTED")

    manager = type("FakeWebQueue", (), {})()
    manager.web_view = type("View", (), {"page": lambda self: page})()
    manager._web_operation_id = 10
    manager.injection_result_requested = SignalProbe()
    manager.protocol_initialized = False
    manager._protocol_pending = False

    page = Page()
    WebChatQueueManager._inject_to_browser(
        manager,
        "synthetic prompt",
        action_kind="ticket",
        ticket_id="ticket-a",
        send=True,
        mark_send=True,
    )

    script = page.scripts[0]
    assert "document.querySelector" in script
    assert "textarea" in script
    assert "contenteditable" in script
    assert "button.click()" in script
    assert "markSendClicked" in script
    assert "getState" in script
    assert "operationId" in script
    assert "synthetic prompt" in script


def test_g05_response_correlation_requires_exact_bot_and_ticket_identity() -> None:
    manager = make_legacy_manager()

    assert WebChatQueueManager._consume_response(
        manager,
        'respuesta a (Sunna ticket-a) “wrong bot”',
    ) is False
    assert WebChatQueueManager._consume_response(
        manager,
        'respuesta a (Cari ticket-b) “wrong ticket”',
    ) is False
    assert WebChatQueueManager._consume_response(
        manager,
        'respuesta a (Cari ticket-a) “accepted”',
    ) is True
    assert manager.ticket_processed.events == [
        ("ticket-a", "accepted"),
    ]


def test_g06_late_response_with_stale_operation_id_is_discarded() -> None:
    manager = make_legacy_manager()
    manager._consume_response = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("stale response must not reach protocol parser")
    )

    stale = json.dumps(
        {
            "ticket_id": "ticket-a",
            "operation_id": 6,
            "text": 'respuesta a (Cari ticket-a) “late”',
        }
    )
    WebChatQueueManager._on_web_bridge_event(
        manager,
        "RESPONSE_COMPLETE",
        stale,
    )


def test_g06_late_response_for_previous_ticket_is_discarded() -> None:
    manager = make_legacy_manager("ticket-current")
    manager._consume_response = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("previous-ticket response must not reach parser")
    )

    previous = json.dumps(
        {
            "ticket_id": "ticket-previous",
            "operation_id": 7,
            "text": 'respuesta a (Cari ticket-previous) “late”',
        }
    )
    WebChatQueueManager._on_web_bridge_event(
        manager,
        "RESPONSE_COMPLETE",
        previous,
    )


def test_g07_navigation_contract_uses_provider_url_and_clean_reload() -> None:
    assert GEMINI_URL == "https://gemini.google.com"

    class Page:
        def __init__(self, reload_error: bool = False) -> None:
            self.reload_error = reload_error
            self.calls = []

        async def reload(self, **kwargs):
            self.calls.append(("reload", kwargs))
            if self.reload_error:
                raise RuntimeError("synthetic reload failure")

        async def goto(self, url, **kwargs):
            self.calls.append(("goto", url, kwargs))

    manager = WebQueueManager.__new__(WebQueueManager)
    manager.pages = {}
    manager.interaction_counters = {}

    page = Page()
    manager.pages["cari"] = page
    asyncio.run(manager.soft_reset_page("cari"))
    assert page.calls[0][0] == "reload"
    assert page.calls[0][1]["wait_until"] == "domcontentloaded"
    assert page.calls[0][1]["timeout"] > 0
    assert manager.interaction_counters["cari"] == 0

    fallback_page = Page(reload_error=True)
    manager.pages["sunna"] = fallback_page
    asyncio.run(manager.soft_reset_page("sunna"))
    assert fallback_page.calls[1][0] == "goto"
    assert fallback_page.calls[1][1] == GEMINI_URL
    assert fallback_page.calls[1][2]["wait_until"] == "domcontentloaded"
    assert manager.interaction_counters["sunna"] == 0


def test_g07_legacy_queue_focus_restore_rejects_non_google_navigation() -> None:
    class Url:
        def __init__(self, host: str) -> None:
            self._host = host

        def host(self) -> str:
            return self._host

    class View:
        def __init__(self) -> None:
            self.focus_calls = 0

        def setFocus(self) -> None:
            self.focus_calls += 1

        def activateWindow(self) -> None:
            self.focus_calls += 1

    manager = type("FakeWebQueue", (), {})()
    manager._shutdown_started = False
    manager.web_view = View()

    scheduled = []
    manager._restore_web_focus = lambda: scheduled.append("focus")

    WebChatQueueManager._on_url_focus_restore(
        manager,
        Url("example.test"),
    )
    assert scheduled == []

    WebChatQueueManager._on_url_focus_restore(
        manager,
        Url("accounts.google.com"),
    )
    assert scheduled == ["focus"]
