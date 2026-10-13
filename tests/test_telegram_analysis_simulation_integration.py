# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bot_ia.config import ProviderConfig
from bot_ia.contracts import UniverseRegistry
from bot_ia.core import LocalBrain, Router
from bot_ia.core.application import BotApplication, InMemorySessionStore
from bot_ia.core.local_workflow import LocalWorkflow
from bot_ia.core.models import Intent, Route
from bot_ia.interfaces.telegram import (
    PollingConfig,
    TelegramApiClient,
    TelegramPoller,
)
from bot_ia.interfaces.telegram_event_ledger import TelegramEventLedger
from bot_ia.interfaces.telegram_projects import TelegramProjectsAdapter
from bot_ia.interfaces.telegram_instance_lock import TelegramInstanceLock
from bot_ia.providers import ProviderResponse, ProviderStatus, ProviderUsage


SIMULATION_JSON = {
    "base": {"ventas": 100},
    "scenarios": [
        {
            "name": "crecimiento",
            "changes": [
                {"metric": "ventas", "operation": "add", "value": 20},
            ],
        },
    ],
}

ANALYSIS_JSON = json.dumps({
    "objective": "Evaluar la propuesta indicada.",
    "assumptions": ["El contenido describe una propuesta que se desea evaluar."],
    "unknowns": ["No se aportaron datos cuantitativos."],
    "alternatives": ["Mantener el estado actual.", "Probar la propuesta en pequeño."],
    "risks": ["La propuesta puede fallar si los supuestos no se cumplen."],
    "recommendation": "Validar los supuestos con una prueba limitada.",
    "next_action": "Definir una métrica de éxito.",
    "limitations": ["El análisis depende del contenido suministrado."],
})


class ControlledTelegramTransport:
    """HTTP transport double: only one getUpdates and sendMessage are allowed."""

    def __init__(self, update: dict[str, object]) -> None:
        self.update = update
        self.calls: list[tuple[str, dict[str, object], float]] = []
        self._updates_returned = False

    def __call__(
        self,
        url: str,
        payload: dict[str, object],
        timeout: float,
    ) -> dict[str, object]:
        method = url.rsplit("/", 1)[-1]
        self.calls.append((method, dict(payload), timeout))
        if method == "getUpdates":
            if self._updates_returned:
                return {"ok": True, "result": []}
            self._updates_returned = True
            return {"ok": True, "result": [self.update]}
        if method == "sendMessage":
            sent_count = sum(call[0] == "sendMessage" for call in self.calls)
            return {
                "ok": True,
                "result": {
                    "message_id": 9000 + sent_count,
                    "chat": {"id": payload.get("chat_id")},
                    "text": payload.get("text", ""),
                },
            }
        raise AssertionError(f"Unexpected Telegram endpoint: {method}")


class FakeProviderManager:
    """ProviderManager-shaped deterministic double; never performs network I/O."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, object, object]] = []

    def execute(self, decision, request, *, fallback_provider=None):
        self.calls.append((decision, request, fallback_provider))
        return SimpleNamespace(
            response=ProviderResponse(
                provider=request.provider,
                model=request.model,
                status=ProviderStatus.SUCCESS,
                output_text=ANALYSIS_JSON,
                usage=ProviderUsage(),
                latency_ms=1,
                request_id=request.request_id,
            )
        )


class TelegramAnalysisSimulationIntegrationTests(unittest.TestCase):
    def _run_update(self, text: str, update_id: int):
        temp = tempfile.TemporaryDirectory(prefix="sim01-telegram-e2e-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        root_patcher = patch("bot_ia.interfaces.telegram.PROJECT_ROOT", root)
        root_patcher.start()
        self.addCleanup(root_patcher.stop)

        chat_id = 7654321
        update = {
            "update_id": update_id,
            "message": {
                "message_id": update_id + 100,
                "from": {
                    "id": 1234567,
                    "is_bot": False,
                    "first_name": "Integration",
                },
                "chat": {"id": chat_id, "type": "private"},
                "date": 1791820800,
                "text": text,
            },
        }
        transport = ControlledTelegramTransport(update)
        client = TelegramApiClient(
            "test-token-not-a-real-credential",
            transport=transport,
            timeout_seconds=1.0,
            max_retries=0,
            retry_delay_seconds=0,
            sleeper=lambda _seconds: None,
        )
        provider = FakeProviderManager()
        workflow = LocalWorkflow(
            {},
            provider_manager=provider,
            provider_config=ProviderConfig(
                provider_id="test-provider",
                model="test-model",
                max_output_tokens=256,
                timeout_seconds=1.0,
            ),
        )
        application = BotApplication(
            LocalBrain(UniverseRegistry()),
            Router(),
            InMemorySessionStore(),
            executor=workflow,
        )
        adapter = TelegramProjectsAdapter(application, SimpleNamespace())
        poller = TelegramPoller(
            client,
            adapter,
            config=PollingConfig(
                poll_timeout_seconds=0,
                idle_delay_seconds=0,
                retry_delay_seconds=0,
                max_consecutive_failures=1,
            ),
            sleeper=lambda _seconds: None,
            event_ledger=TelegramEventLedger(root / "events.sqlite3"),
            instance_lock=TelegramInstanceLock(client.token, root),
        )
        self.addCleanup(adapter.close)
        self.addCleanup(poller.stop)
        return {
            "root": root,
            "chat_id": chat_id,
            "transport": transport,
            "provider": provider,
            "workflow": workflow,
            "application": application,
            "adapter": adapter,
            "poller": poller,
        }

    def _assert_delivery(self, context, update_id: int):
        transport = context["transport"]
        poller = context["poller"]
        result = poller.run(max_cycles=1)

        self.assertEqual(result.polls, 1)
        self.assertEqual(result.updates_received, 1)
        self.assertEqual(result.updates_processed, 1)
        self.assertEqual(result.updates_skipped, 0)
        self.assertEqual(result.responses_sent, 1)
        self.assertEqual(result.transport_errors, 0)
        self.assertEqual(poller.offset, update_id + 1)

        methods = [method for method, _payload, _timeout in transport.calls]
        self.assertEqual(methods, ["getUpdates", "sendMessage"])
        sent = [
            payload
            for method, payload, _timeout in transport.calls
            if method == "sendMessage"
        ]
        self.assertEqual(len(sent), 1)
        self.assertEqual(str(context["chat_id"]), str(sent[0]["chat_id"]))
        self.assertTrue(sent[0].get("text"))
        self.assertFalse(
            any(method not in {"getUpdates", "sendMessage"} for method in methods),
            "transport rejected any unexpected Telegram endpoint",
        )
        return result, sent[0]

    def test_simular_runs_through_poller_adapter_application_and_delivery(self):
        command = "/simular " + json.dumps(SIMULATION_JSON, separators=(",", ":"))
        context = self._run_update(command, 4101)
        app = context["application"]
        workflow = context["workflow"]
        responses = []
        original_handle = app.handle

        def capture_response(request):
            response = original_handle(request)
            responses.append(response)
            return response

        with (
            patch.object(app, "handle", side_effect=capture_response) as handle_spy,
            patch.object(
                workflow,
                "execute_analysis",
                wraps=workflow.execute_analysis,
            ) as analysis_spy,
        ):
            _result, payload = self._assert_delivery(context, 4101)

        self.assertEqual(handle_spy.call_count, 1, "poller must pass the update into BotApplication")
        self.assertEqual(len(responses), 1)
        response = responses[0]
        self.assertEqual(response.brain.intent, Intent.SIMULATION)
        self.assertEqual(response.decision.route, Route.LOCAL)
        self.assertEqual(response.execution.status, "completed")
        metrics = {
            metric["metric"]: metric
            for metric in response.execution.scenarios[0]["metrics"]
        }
        self.assertEqual(metrics["ventas"]["final_value"], 120)
        self.assertIn("120", payload["text"])
        self.assertEqual(analysis_spy.call_count, 0)
        self.assertEqual(context["provider"].calls, [])
        self.assertEqual(
            [method for method, _payload, _timeout in context["transport"].calls],
            ["getUpdates", "sendMessage"],
        )

    def test_analizar_runs_through_poller_adapter_workflow_and_delivery(self):
        context = self._run_update("/analizar contenido de prueba", 4102)
        app = context["application"]
        workflow = context["workflow"]
        responses = []
        original_handle = app.handle

        def capture_response(request):
            response = original_handle(request)
            responses.append(response)
            return response

        with (
            patch.object(app, "handle", side_effect=capture_response) as handle_spy,
            patch.object(
                workflow,
                "execute_analysis",
                wraps=workflow.execute_analysis,
            ) as analysis_spy,
        ):
            _result, payload = self._assert_delivery(context, 4102)

        self.assertEqual(handle_spy.call_count, 1, "poller must pass the update into BotApplication")
        self.assertEqual(len(responses), 1)
        response = responses[0]
        self.assertEqual(response.brain.intent, Intent.ANALYSIS)
        self.assertEqual(response.decision.route, Route.LLM)
        self.assertTrue(response.decision.requires_llm)
        self.assertEqual(analysis_spy.call_count, 1)
        self.assertEqual(len(context["provider"].calls), 1)
        self.assertEqual(response.execution.status, "completed")
        report = response.execution.report
        self.assertIsNotNone(report)
        self.assertEqual(report.content_analyzed, "contenido de prueba")
        self.assertFalse(report.evidence_available)
        self.assertEqual(report.evidence_references, ())
        self.assertIn("No se recuperó evidencia documental", report.evidence_status)
        self.assertIn("Evaluar la propuesta indicada", payload["text"])
        self.assertNotIn("source_id=", payload["text"])
        self.assertEqual(
            [method for method, _payload, _timeout in context["transport"].calls],
            ["getUpdates", "sendMessage"],
        )


    def _seed_pending_state(self, context, pending: str) -> tuple[str, str]:
        adapter = context["adapter"]
        key = ("1234567", str(context["chat_id"]))
        adapter._pending[key] = pending
        adapter._selected_main[key] = "stale-main-selection"
        adapter._selected_secondary[key] = "stale-secondary-selection"
        adapter._context_selection[key] = {0}
        adapter._fallback_query[key] = "stale fallback query"
        return key

    def test_explicit_commands_precede_all_pending_input_modes(self):
        pending_states = ("new_novel", "local", "prompt", "edit:wording")
        update_id = 4200
        for command_kind in ("simular", "analizar"):
            for pending in pending_states:
                with self.subTest(command=command_kind, pending=pending):
                    current_id = update_id
                    update_id += 1
                    if command_kind == "simular":
                        command = "/simular " + json.dumps(SIMULATION_JSON, separators=(",", ":"))
                    else:
                        command = "/analizar contenido limpio de prueba"
                    context = self._run_update(command, current_id)
                    key = self._seed_pending_state(context, pending)
                    app = context["application"]
                    workflow = context["workflow"]
                    captured = []
                    responses = []
                    original_handle = app.handle

                    def capture(request):
                        captured.append(request)
                        response = original_handle(request)
                        responses.append(response)
                        return response

                    with (
                        patch.object(app, "handle", side_effect=capture) as handle_spy,
                        patch.object(workflow, "execute_analysis", wraps=workflow.execute_analysis) as analysis_spy,
                    ):
                        _result, payload = self._assert_delivery(context, current_id)

                    self.assertEqual(handle_spy.call_count, 1)
                    self.assertEqual(len(captured), 1)
                    self.assertEqual(captured[0].message, command)
                    self.assertNotIn(key, context["adapter"]._pending)
                    self.assertNotIn(key, context["adapter"]._selected_main)
                    self.assertNotIn(key, context["adapter"]._selected_secondary)
                    self.assertNotIn(key, context["adapter"]._context_selection)
                    self.assertNotIn(key, context["adapter"]._fallback_query)
                    self.assertEqual(len(responses), 1)
                    response = responses[0]
                    if command_kind == "simular":
                        self.assertEqual(response.brain.intent, Intent.SIMULATION)
                        self.assertEqual(response.decision.route, Route.LOCAL)
                        self.assertEqual(response.execution.status, "completed")
                        self.assertEqual(analysis_spy.call_count, 0)
                        self.assertEqual(context["provider"].calls, [])
                        self.assertIn('"final_value": 120', payload["text"])
                    else:
                        self.assertEqual(response.brain.intent, Intent.ANALYSIS)
                        self.assertEqual(response.decision.route, Route.LLM)
                        self.assertEqual(analysis_spy.call_count, 1)
                        self.assertEqual(len(context["provider"].calls), 1)
                        report = response.execution.report
                        self.assertIsNotNone(report)
                        self.assertEqual(report.content_analyzed, "contenido limpio de prueba")
                        self.assertIn("Evaluar la propuesta indicada", payload["text"])
                    self.assertEqual(
                        [method for method, _payload, _timeout in context["transport"].calls],
                        ["getUpdates", "sendMessage"],
                    )

    def test_ordinary_message_still_consumes_existing_pending_mode(self):
        context = self._run_update("un boceto breve de escena", 4301)
        key = self._seed_pending_state(context, "local")
        app = context["application"]
        with patch.object(app, "handle", wraps=app.handle) as handle_spy:
            _result, payload = self._assert_delivery(context, 4301)
        self.assertEqual(handle_spy.call_count, 0)
        self.assertNotIn(key, context["adapter"]._pending)
        self.assertTrue(payload["text"])
        self.assertEqual(
            [method for method, _payload, _timeout in context["transport"].calls],
            ["getUpdates", "sendMessage"],
        )

    def test_command_prefix_collision_does_not_override_pending_mode(self):
        context = self._run_update("/simularx esto es texto ordinario", 4302)
        key = self._seed_pending_state(context, "local")
        app = context["application"]
        with patch.object(app, "handle", wraps=app.handle) as handle_spy:
            _result, payload = self._assert_delivery(context, 4302)
        self.assertEqual(handle_spy.call_count, 0)
        self.assertNotIn(key, context["adapter"]._pending)
        self.assertTrue(payload["text"])


if __name__ == "__main__":
    unittest.main()
