# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bot_ia.config import ProviderConfig
from bot_ia.contracts import UniverseRegistry
from bot_ia.core import LocalBrain, Router
from bot_ia.core.analysis_simulation import (
    AnalysisResult,
    SimulationInputError,
    execute_simulation_command,
    simulate_json,
)
from bot_ia.core.application import ApplicationRequest, BotApplication, InMemorySessionStore
from bot_ia.core.intents import IntentClassifier, normalize_message
from bot_ia.core.local_workflow import LocalWorkflow
from bot_ia.core.models import Intent, Route
from bot_ia.providers import ProviderResponse, ProviderStatus, ProviderUsage


SAMPLE = {
    "base": {"ventas": 100, "coste": 50, "beneficio": 0},
    "scenarios": [
        {
            "name": "crecimiento",
            "changes": [
                {"metric": "ventas", "operation": "add", "value": 20},
                {"metric": "coste", "operation": "multiply", "value": 1.1},
                {"metric": "beneficio", "operation": "set", "value": 15},
            ],
        },
        {
            "name": "recorte",
            "changes": [{"metric": "coste", "operation": "add", "value": -5}],
        },
    ],
}


class FakeProviderManager:
    def __init__(self, output: str | None = None, status=ProviderStatus.SUCCESS):
        self.output = output
        self.status = status
        self.calls = []

    def execute(self, decision, request, *, fallback_provider=None):
        self.calls.append((decision, request, fallback_provider))
        response = ProviderResponse(
            provider=request.provider,
            model=request.model,
            status=self.status,
            output_text=self.output,
            usage=ProviderUsage(),
            latency_ms=1,
            request_id=request.request_id,
        )
        return SimpleNamespace(response=response)


def valid_analysis_json() -> str:
    return json.dumps({
        "objective": "Evaluar la propuesta indicada.",
        "assumptions": ["El contenido describe la propuesta que se desea evaluar."],
        "unknowns": ["No se aportaron datos de costes ni plazos."],
        "alternatives": ["Mantener el estado actual.", "Probar la propuesta en una muestra limitada."],
        "risks": ["La propuesta puede fallar si los supuestos no se cumplen."],
        "recommendation": "Validar primero los supuestos con una prueba limitada.",
        "next_action": "Definir una métrica de éxito y una muestra de prueba.",
        "limitations": ["El análisis depende del contenido suministrado."],
    })


class SimulationTests(unittest.TestCase):
    def test_reference_scenario_operations_and_determinism(self):
        payload = json.dumps(SAMPLE)
        first = simulate_json(payload)
        second = simulate_json(payload)
        self.assertEqual(first.to_dict(), second.to_dict())
        metrics = {item["metric"]: item for item in first.scenarios[0]["metrics"]}
        self.assertEqual(120, metrics["ventas"]["final_value"])
        self.assertEqual(55.00000000000001, metrics["coste"]["final_value"])
        self.assertEqual(15, metrics["beneficio"]["final_value"])
        self.assertEqual(20, metrics["ventas"]["absolute_difference"])
        self.assertEqual(20.0, metrics["ventas"]["percentage_difference"])
        self.assertIsNone(metrics["beneficio"]["percentage_difference"])
        self.assertIn("base es cero", metrics["beneficio"]["percentage_explanation"])

    def test_set_add_and_multiply(self):
        result = simulate_json(json.dumps({
            "base": {"x": 10, "y": 5, "z": 4},
            "scenarios": [{"name": "ops", "changes": [
                {"metric": "x", "operation": "set", "value": 7},
                {"metric": "y", "operation": "add", "value": 3},
                {"metric": "z", "operation": "multiply", "value": 2},
            ]}],
        }))
        values = {item["metric"]: item["final_value"] for item in result.scenarios[0]["metrics"]}
        self.assertEqual({"x": 7, "y": 8, "z": 8}, values)

    def test_scenarios_are_independent_and_input_is_not_mutated(self):
        data = json.loads(json.dumps(SAMPLE))
        before = json.loads(json.dumps(data))
        result = simulate_json(json.dumps(data))
        self.assertEqual(before, data)
        scenarios = {scenario["name"]: scenario for scenario in result.scenarios}
        recorte = {item["metric"]: item for item in scenarios["recorte"]["metrics"]}
        self.assertEqual(50, recorte["coste"]["base_value"])
        self.assertEqual(45, recorte["coste"]["final_value"])
        self.assertEqual(100, recorte["ventas"]["final_value"])

    def test_rejects_invalid_json_and_missing_payload(self):
        with self.assertRaises(SimulationInputError):
            simulate_json("{")
        self.assertEqual("invalid", execute_simulation_command("/simular").status)

    def test_rejects_unknown_operations_and_metrics(self):
        for change in (
            {"metric": "x", "operation": "divide", "value": 2},
            {"metric": "missing", "operation": "add", "value": 2},
        ):
            payload = {"base": {"x": 1}, "scenarios": [{"name": "s", "changes": [change]}]}
            with self.assertRaises(SimulationInputError):
                simulate_json(json.dumps(payload))

    def test_rejects_boolean_nan_and_infinity(self):
        invalid_payloads = [
            '{"base":{"x":true},"scenarios":[{"name":"s","changes":[{"metric":"x","operation":"add","value":1}]}]}',
            '{"base":{"x":1},"scenarios":[{"name":"s","changes":[{"metric":"x","operation":"add","value":NaN}]}]}',
            '{"base":{"x":Infinity},"scenarios":[{"name":"s","changes":[{"metric":"x","operation":"add","value":1}]}]}',
            json.dumps({"base": {"x": 1e308}, "scenarios": [{"name": "s", "changes": [{"metric": "x", "operation": "multiply", "value": 1e308}]}]}),
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(SimulationInputError):
                simulate_json(payload)

    def test_rejects_empty_structures(self):
        invalid = [
            {"base": {}, "scenarios": [{"name": "s", "changes": [{"metric": "x", "operation": "add", "value": 1}]}]},
            {"base": {"x": 1}, "scenarios": []},
            {"base": {"x": 1}, "scenarios": [{"name": "s", "changes": []}]},
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(SimulationInputError):
                simulate_json(json.dumps(item))

    def test_repeated_metric_changes_are_applied_sequentially(self):
        result = simulate_json(json.dumps({
            "base": {"ventas": 10},
            "scenarios": [{"name": "secuencial", "changes": [
                {"metric": "ventas", "operation": "add", "value": 2},
                {"metric": "ventas", "operation": "multiply", "value": 3},
            ]}],
        }))
        self.assertEqual("completed", result.status)
        self.assertEqual(1, len(result.scenarios))
        self.assertEqual(36, result.scenarios[0]["metrics"][0]["final_value"])

    def test_deeply_nested_json_becomes_controlled_input_error(self):
        depth = sys.getrecursionlimit() + 100
        payload = "[" * depth + "0" + "]" * depth
        with self.assertRaises(SimulationInputError) as raised:
            simulate_json(payload)
        self.assertNotIsInstance(raised.exception, RecursionError)
        message = str(raised.exception).lower()
        self.assertTrue(
            "anidado" in message
            or "el objeto raíz debe contener únicamente 'base' y 'scenarios'" in message,
            f"unexpected controlled validation message: {message}",
        )

    def test_json_decoder_recursion_error_becomes_controlled_depth_error(self):
        with patch(
            "bot_ia.core.analysis_simulation.json.loads",
            side_effect=RecursionError("simulated decoder recursion"),
        ):
            with self.assertRaises(SimulationInputError) as raised:
                simulate_json('{"base": {}, "scenarios": []}')
        self.assertIn("excesivamente anidado", str(raised.exception).lower())

    def test_invalid_later_scenario_publishes_no_partial_results(self):
        payload = {
            "base": {"ventas": 10},
            "scenarios": [
                {"name": "valido", "changes": [
                    {"metric": "ventas", "operation": "add", "value": 2},
                ]},
                {"name": "invalido", "changes": [
                    {"metric": "desconocida", "operation": "add", "value": 1},
                ]},
            ],
        }
        result = execute_simulation_command("/simular " + json.dumps(payload))
        self.assertEqual("invalid", result.status)
        self.assertEqual((), result.scenarios)

    def test_deeply_nested_json_is_controlled_through_application(self):
        depth = sys.getrecursionlimit() + 100
        nested = "[" * depth + "0" + "]" * depth
        payload = (
            '{"base":{"ventas":10},"scenarios":[{"name":"valido","changes":'
            '[{"metric":"ventas","operation":"add","value":2}]}],"extra":'
            + nested
            + "}"
        )
        app = BotApplication(LocalBrain(UniverseRegistry()), Router(), InMemorySessionStore())
        response = app.handle(ApplicationRequest("u", "c", "/simular " + payload))
        self.assertEqual("invalid", response.execution.status)
        self.assertEqual((), response.execution.scenarios)
        self.assertIn("No se ejecutó la simulación", response.text)

    def test_rejects_duplicate_json_keys(self):
        payload = '{"base":{"x":1},"scenarios":[{"name":"s","name":"s2","changes":[{"metric":"x","operation":"add","value":1}]}]}'
        with self.assertRaises(SimulationInputError):
            simulate_json(payload)

    def test_command_routes_and_runs_without_provider_or_universe(self):
        class ExplodingExecutor:
            def execute(self, *_args, **_kwargs):
                raise AssertionError("simulation must not call workflow/provider")
            def execute_analysis(self, *_args, **_kwargs):
                raise AssertionError("simulation must not call analysis provider")

        app = BotApplication(LocalBrain(UniverseRegistry()), Router(), InMemorySessionStore(), executor=ExplodingExecutor())
        response = app.handle(ApplicationRequest("u", "c", "/simular " + json.dumps({
            "base": {"ventas": 100},
            "scenarios": [{"name": "s", "changes": [{"metric": "ventas", "operation": "add", "value": 5}]}],
        })))
        self.assertEqual(Intent.SIMULATION, response.brain.intent)
        self.assertEqual(Route.LOCAL, response.decision.route)
        self.assertEqual("completed", response.execution.status)
        self.assertIn('"final_value": 105', response.text)

    def test_invalid_simulation_is_controlled_through_application(self):
        app = BotApplication(LocalBrain(UniverseRegistry()), Router(), InMemorySessionStore())
        response = app.handle(ApplicationRequest("u", "c", "/simular {no-json"))
        self.assertEqual("invalid", response.execution.status)
        self.assertIn("No se ejecutó", response.text)


class AnalysisTests(unittest.TestCase):
    def make_workflow(self, provider_manager):
        return LocalWorkflow(
            {},
            provider_manager=provider_manager,
            provider_config=ProviderConfig(provider_id="fake", model="fake-model"),
        )

    def make_app(self, workflow):
        return BotApplication(LocalBrain(UniverseRegistry()), Router(), InMemorySessionStore(), executor=workflow)

    def test_explicit_classification_and_routing(self):
        classifier = IntentClassifier()
        self.assertIs(Intent.ANALYSIS, classifier.classify(normalize_message("/analizar propuesta")))
        self.assertIs(Intent.SIMULATION, classifier.classify(normalize_message("/simular {}")))
        brain = LocalBrain(UniverseRegistry()).process(
            __import__("bot_ia.core.models", fromlist=["BrainRequest"]).BrainRequest("/analizar propuesta", "u", "c", None)
        )
        decision = Router().decide(brain)
        self.assertIs(Intent.ANALYSIS, decision.intent)
        self.assertIs(Route.LLM, decision.route)
        self.assertTrue(decision.requires_llm)

    def test_analysis_runs_from_application_through_existing_provider(self):
        provider = FakeProviderManager(valid_analysis_json())
        response = self.make_app(self.make_workflow(provider)).handle(
            ApplicationRequest("u", "c", "/analizar evaluar esta propuesta")
        )
        self.assertEqual("completed", response.execution.status)
        self.assertEqual(1, len(provider.calls))
        self.assertIn("ANÁLISIS ESTRUCTURADO — COMPLETADO", response.text)
        self.assertEqual("evaluar esta propuesta", response.execution.report.content_analyzed)
        self.assertFalse(response.execution.report.evidence_available)
        self.assertEqual((), response.execution.report.evidence_references)
        self.assertTrue(any("no se recuperaron" in item.lower() for item in response.execution.report.limitations))

    def test_analysis_schema_distinguishes_content_evidence_and_unknowns(self):
        provider = FakeProviderManager(valid_analysis_json())
        result = self.make_app(self.make_workflow(provider)).handle(
            ApplicationRequest("u", "c", "/analizar contenido de usuario")
        ).execution
        report = result.report
        self.assertEqual("contenido de usuario", report.content_analyzed)
        self.assertIn("No se aportaron datos de costes ni plazos.", report.unknowns)
        self.assertFalse(report.evidence_available)
        self.assertEqual("completed", result.status)

    def test_empty_analysis_command_is_controlled(self):
        result = self.make_app(self.make_workflow(FakeProviderManager(valid_analysis_json()))).handle(
            ApplicationRequest("u", "c", "/analizar")
        )
        self.assertEqual("invalid", result.execution.status)
        self.assertEqual("invalid_analysis_input", result.execution.error_code)

    def test_missing_provider_is_controlled_not_a_fake_analysis(self):
        result = self.make_app(self.make_workflow(None)).handle(
            ApplicationRequest("u", "c", "/analizar propuesta")
        )
        self.assertEqual("unavailable", result.execution.status)
        self.assertIsNone(result.execution.report)
        self.assertIn("No se completó el análisis", result.text)

    def test_provider_error_and_invalid_output_are_controlled(self):
        failed = self.make_app(self.make_workflow(FakeProviderManager(None, ProviderStatus.ERROR))).handle(
            ApplicationRequest("u", "c", "/analizar propuesta")
        )
        malformed = self.make_app(self.make_workflow(FakeProviderManager('{"objective":"incomplete","evidence_references":["invented-source"]}'))).handle(
            ApplicationRequest("u", "c", "/analizar propuesta")
        )
        self.assertEqual("unavailable", failed.execution.status)
        self.assertEqual("invalid_provider_output", malformed.execution.error_code)

    def test_normal_messages_keep_existing_local_behavior(self):
        app = BotApplication(LocalBrain(UniverseRegistry()), Router(), InMemorySessionStore())
        response = app.handle(ApplicationRequest("u", "c", "Hola."))
        self.assertEqual(Intent.GREETING, response.brain.intent)
        self.assertEqual(Route.LOCAL, response.decision.route)
        self.assertIn("¡Hola!", response.text)


if __name__ == "__main__":
    unittest.main()
