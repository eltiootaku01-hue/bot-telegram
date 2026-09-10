from pathlib import Path
import tempfile
import unittest

from bot_ia.agents import PolicyRule, RulePriority
from bot_ia.contracts import AuthorityLevel, CanonStatus, Confidence, SourceStatus, UniverseDefinition, UniverseRegistry
from bot_ia.core import LocalBrain, Router
from bot_ia.core.application import ApplicationRequest, BotApplication, InMemorySessionStore
from bot_ia.core.local_workflow import LocalWorkflow
from bot_ia.interfaces.telegram import TelegramAdapter
from bot_ia.librarian import SourceInventory, SourceMetadata, SourceType
from bot_ia.memory import MemoryStore, MemoryType
from bot_ia.providers import ProviderManager, ProviderResponse, ProviderStatus, ProviderUsage


class FakeLocalProvider:
    provider_id = "local_fake"
    def generate(self, request):
        return ProviderResponse("local_fake", request.model, ProviderStatus.SUCCESS, "Respuesta local simulada.", ProviderUsage(), 0, request.request_id)


class Phase9IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = UniverseRegistry()
        for universe in ("alpha_world", "beta_world"):
            self.registry.register(UniverseDefinition(universe, universe, root / universe))
        entries = {}
        for universe, text in (("alpha_world", "Kuro protege Alpha."), ("beta_world", "Kuro protege Beta.")):
            folder = root / universe
            folder.mkdir()
            (folder / "fact.md").write_text(text, encoding="utf-8")
            entries[universe] = SourceInventory(folder).discover(universe, {"fact.md": SourceMetadata(f"{universe}_fact", SourceType.CHAPTER, AuthorityLevel.PRIMARY, SourceStatus.VALIDATED, CanonStatus.CANON)})
        self.memory = MemoryStore(root, self.registry)
        self.workflow = LocalWorkflow(entries, memory_store=self.memory, provider_manager=ProviderManager((FakeLocalProvider(),)))
        self.app = BotApplication(LocalBrain(self.registry), Router(), InMemorySessionStore(), default_universe_id="alpha_world", executor=self.workflow)

    def tearDown(self) -> None:
        self.memory.close()
        self.temp.cleanup()

    def handle(self, message: str, *, user: str = "u1", conversation: str = "c1"):
        return self.app.handle(ApplicationRequest(user, conversation, message))

    def test_casual_uses_application_without_search(self) -> None:
        response = self.handle("Hola, ¿qué tal?")
        self.assertFalse(response.execution.searched)
        self.assertEqual("casual", response.execution.agent_result.output_contract.response_type.value)
        self.assertTrue(response.execution.agent_result.output_contract.validate().valid)

    def test_factual_search_reaches_evidence_agent_and_contract(self) -> None:
        response = self.handle("¿Quién es Kuro?")
        execution = response.execution
        self.assertTrue(execution.searched)
        self.assertTrue(execution.agent_result.output_contract.used_evidence)
        self.assertTrue(execution.agent_result.output_contract.validate().valid)

    def test_ambiguous_question_requests_clarification_without_identity(self) -> None:
        response = self.handle("¿Ella quién es?")
        contract = response.execution.agent_result.output_contract
        self.assertTrue(contract.needs_clarification)
        self.assertEqual("Necesito una aclaración para continuar.", response.text)
        self.assertFalse(contract.used_evidence)

    def test_opinion_and_proposal_are_not_facts(self) -> None:
        opinion = self.handle("¿Qué te parece Kuro?").execution.agent_result.output_contract
        proposal = self.handle("Kuro podría viajar.").execution.agent_result.output_contract
        self.assertEqual("opinion", opinion.response_type.value)
        self.assertEqual("proposal", proposal.response_type.value)

    def test_missing_evidence_fails_closed(self) -> None:
        response = self.handle("¿Quién es Nadie?")
        contract = response.execution.agent_result.output_contract
        self.assertFalse(contract.evidence_sufficient)
        self.assertEqual("contract_validation_failed", contract.uncertainty)
        self.assertTrue(contract.needs_clarification)
        self.assertEqual("Necesito una aclaración para continuar.", response.text)

    def test_authorized_memory_enters_context_and_unapproved_memory_does_not(self) -> None:
        approved = self.memory.propose(universe_id="alpha_world", user_id="u1", conversation_id="c1", memory_type=MemoryType.PREFERENCE, content="Kuro favorito", source="user", provenance="test")
        self.memory.approve(approved.memory_id, approved_by_author="author")
        self.memory.propose(universe_id="alpha_world", user_id="u1", conversation_id="c1", memory_type=MemoryType.NOTE, content="Kuro secreto", source="user", provenance="test")
        contract = self.handle("Kuro").execution.agent_result.output_contract
        self.assertEqual((f"memory:{approved.memory_id}",), contract.used_memory)
        self.assertTrue(contract.memory_authorized)

    def test_universes_do_not_cross_evidence(self) -> None:
        beta_app = BotApplication(LocalBrain(self.registry), Router(), InMemorySessionStore(), default_universe_id="beta_world", executor=self.workflow)
        contract = beta_app.handle(ApplicationRequest("u1", "beta", "¿Quién es Kuro?")).execution.agent_result.output_contract
        self.assertEqual(("beta_world_fact",), contract.used_evidence)

    def test_provider_is_local_fake_and_contract_survives(self) -> None:
        contract = self.handle("Escribe una escena.").execution.agent_result.output_contract
        response = self.handle("Escribe una escena.").execution.provider_response
        self.assertEqual("local_fake", response.provider)
        self.assertEqual("Respuesta local simulada.", contract.answer)

    def test_higher_priority_conflict_is_recorded_and_lower_is_blocked(self) -> None:
        def rules(*_):
            return (PolicyRule("security", RulePriority.SECURITY_NO_INVENTION, "facts", "do_not_invent"), PolicyRule("personality", RulePriority.IA_CHAN_PERSONALITY, "facts", "sound_certain"))
        app = BotApplication(LocalBrain(self.registry), Router(), InMemorySessionStore(), default_universe_id="alpha_world", executor=LocalWorkflow({}, rule_factory=rules))
        execution = app.handle(ApplicationRequest("u", "c", "Hola")).execution
        self.assertEqual("security", execution.rule_resolution.conflicts[0].winner_rule_id)
        self.assertIn("personality", execution.rule_resolution.conflicts[0].blocked_rule_ids)

    def test_fake_telegram_adapter_reaches_local_workflow(self) -> None:
        outbound = TelegramAdapter(self.app).handle_update({"message": {"from": {"id": 1}, "chat": {"id": 2}, "text": "Hola, ¿qué tal?"}})
        self.assertEqual("local", outbound.route)


if __name__ == "__main__":
    unittest.main()
