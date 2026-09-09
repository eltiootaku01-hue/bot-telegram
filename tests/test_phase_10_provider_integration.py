from pathlib import Path
import tempfile
import unittest

from bot_ia.contracts import (
    AuthorityLevel,
    CanonStatus,
    SourceStatus,
    UniverseDefinition,
    UniverseRegistry,
)
from bot_ia.core import LocalBrain, Router
from bot_ia.core.application import (
    ApplicationRequest,
    BotApplication,
    InMemorySessionStore,
)
from bot_ia.core.local_workflow import LocalWorkflow
from bot_ia.librarian import SourceInventory, SourceMetadata, SourceType
from bot_ia.memory import MemoryStore
from bot_ia.providers import (
    GeminiProvider,
    ProviderManager,
    ProviderStatus,
)


class FakeGeminiTransport:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return {
            "steps": [
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": "Respuesta generada por Gemini.",
                        }
                    ],
                }
            ],
            "usage": {
                "total_input_tokens": 10,
                "total_output_tokens": 6,
                "total_tokens": 16,
            },
        }


class Phase10ProviderIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)

        self.registry = UniverseRegistry()
        self.registry.register(
            UniverseDefinition(
                "alpha_world",
                "Alpha",
                root / "alpha_world",
            )
        )

        folder = root / "alpha_world"
        folder.mkdir()

        (folder / "fact.md").write_text(
            "Kuro protege Alpha.",
            encoding="utf-8",
        )

        entries = {
            "alpha_world": SourceInventory(folder).discover(
                "alpha_world",
                {
                    "fact.md": SourceMetadata(
                        "alpha_fact",
                        SourceType.CHAPTER,
                        AuthorityLevel.PRIMARY,
                        SourceStatus.VALIDATED,
                        CanonStatus.CANON,
                    )
                },
            )
        }

        self.transport = FakeGeminiTransport()
        gemini = GeminiProvider(
            key_loader=lambda _: "test-key",
            transport=self.transport,
        )

        self.memory = MemoryStore(root, self.registry)

        self.workflow = LocalWorkflow(
            entries,
            memory_store=self.memory,
            provider_manager=ProviderManager((gemini,)),
            provider_id="gemini",
            provider_model="gemini-test",
        )

        self.app = BotApplication(
            LocalBrain(self.registry),
            Router(),
            InMemorySessionStore(),
            default_universe_id="alpha_world",
            executor=self.workflow,
        )

    def tearDown(self) -> None:
        self.memory.close()
        self.temp.cleanup()

    def handle(self, message: str):
        return self.app.handle(
            ApplicationRequest("u1", "c1", message)
        )

    def test_llm_route_reaches_configured_gemini(self) -> None:
        response = self.handle("Escribe una escena.")
        provider_response = response.execution.provider_response

        self.assertIsNotNone(provider_response)
        self.assertEqual("gemini", provider_response.provider)
        self.assertEqual(ProviderStatus.SUCCESS, provider_response.status)
        self.assertEqual(
            "Respuesta generada por Gemini.",
            response.text,
        )

    def test_gemini_receives_prepared_agent_output(self) -> None:
        response = self.handle("Escribe una escena.")

        self.assertEqual(1, len(self.transport.calls))
        payload = self.transport.calls[0]["payload"]

        self.assertEqual("gemini-test", payload["model"])
        text = payload["input"]

        self.assertIn("UNIVERSE: alpha_world", text)
        self.assertIn("INTENT: creative_writing", text)
        self.assertIn("Do not invent established facts.", text)
        self.assertIn(
            "Treat the supplied context as the source of truth for the project.",
            text,
        )
        self.assertIn("security_no_invention: factual_output -> evidence_required", text)
        self.assertIn("CONTEXT:", text)
        self.assertIn("USER REQUEST:", text)
        self.assertIn("Escribe una escena.", text)
        self.assertEqual(
            "gemini-test",
            response.execution.provider_response.model,
        )

    def test_search_route_uses_evidence_gate_without_calling_provider(self) -> None:
        response = self.handle("¿Quién es Kuro?")

        self.assertIsNone(response.execution.provider_response)
        self.assertEqual("Kuro protege Alpha.", response.text)
        self.assertEqual(0, len(self.transport.calls))
        self.assertIn("Kuro protege Alpha.", response.execution.context.text)

    def test_local_route_does_not_call_gemini(self) -> None:
        response = self.handle("Hola.")

        self.assertEqual(0, len(self.transport.calls))
        self.assertIsNone(response.execution.provider_response)

    def test_provider_configuration_is_not_stored_in_request_content(self) -> None:
        response = self.handle("Escribe una escena.")
        provider_response = response.execution.provider_response

        self.assertIsNotNone(provider_response)
        self.assertEqual("gemini", provider_response.provider)
        self.assertEqual("gemini-test", provider_response.model)
        self.assertNotIn("test-key", response.execution.agent_result.answer)

    def test_usage_is_preserved_from_provider(self) -> None:
        response = self.handle("Escribe una escena.")
        usage = response.execution.provider_response.usage

        self.assertEqual(10, usage.input_tokens)
        self.assertEqual(6, usage.output_tokens)
        self.assertEqual(16, usage.total_tokens)


if __name__ == "__main__":
    unittest.main()
