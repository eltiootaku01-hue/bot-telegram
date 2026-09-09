from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from bot_ia.contracts import UniverseDefinition, UniverseRegistry, SessionState
from bot_ia.core import BrainRequest, EntityCandidate, LocalBrain, Route, Router

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


class Phase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = UniverseRegistry()
        self.registry.register(UniverseDefinition("one_neko_punch", "One Neko Punch", Path("data/one")))
        self.registry.register(UniverseDefinition("other_world", "Other World", Path("data/other")))
        self.brain = LocalBrain(self.registry)
        self.router = Router()
        self.state = SessionState("s1", "one_neko_punch", NOW + timedelta(hours=1), chapter_id="chapter_1", mode="draft")

    def run_message(self, message: str, *, state: SessionState | None = None, candidates: tuple[EntityCandidate, ...] = ()): 
        result = self.brain.process(BrainRequest(message, "u1", "c1", self.state if state is None else state, candidates=candidates))
        return result, self.router.decide(result)

    def test_greeting_routes_local(self) -> None:
        _, decision = self.run_message("Hola")
        self.assertEqual(Route.LOCAL, decision.route)

    def test_help_routes_local(self) -> None:
        _, decision = self.run_message("Ayuda")
        self.assertEqual(Route.LOCAL, decision.route)

    def test_factual_question_routes_search_without_search_execution(self) -> None:
        _, decision = self.run_message("Quien es Kuro?")
        self.assertEqual(Route.SEARCH, decision.route)
        self.assertTrue(decision.requires_search)

    def test_creative_request_routes_llm_without_provider(self) -> None:
        _, decision = self.run_message("Escribe una escena breve")
        self.assertEqual(Route.LLM, decision.route)
        self.assertTrue(decision.requires_llm)

    def test_editorial_review_routes_agent_without_agent_execution(self) -> None:
        _, decision = self.run_message("Revisa este dialogo")
        self.assertEqual(Route.AGENT, decision.route)
        self.assertTrue(decision.requires_agent)

    def test_ambiguous_pronoun_routes_clarification(self) -> None:
        candidates = (EntityCandidate("hitomi", "one_neko_punch", "Hitomi"), EntityCandidate("fubuki", "one_neko_punch", "Fubuki"))
        result, decision = self.run_message("Hitomi hablo con Fubuki. Ella respondio.", candidates=candidates)
        self.assertTrue(result.ambiguity)
        self.assertEqual("ambiguous_reference", result.clarification)
        self.assertEqual(Route.CLARIFICATION, decision.route)

    def test_valid_universe_change_is_accepted_and_updates_state(self) -> None:
        result, decision = self.run_message("Cambiar al universo other_world")
        self.assertEqual("updated", result.state_status)
        self.assertEqual("other_world", self.state.universe_id)
        self.assertIsNone(self.state.chapter_id)
        self.assertEqual(Route.LOCAL, decision.route)

    def test_unknown_universe_change_is_rejected_without_state_change(self) -> None:
        result, decision = self.run_message("Cambiar al universo missing_world")
        self.assertEqual("rejected", result.state_status)
        self.assertEqual("one_neko_punch", self.state.universe_id)
        self.assertEqual("unknown_universe", result.clarification)
        self.assertEqual(Route.LOCAL, decision.route)

    def test_alias_with_descriptor_resolves_by_base_name(self) -> None:
        candidates = (
            EntityCandidate(
                "char-na-maid-gata",
                "one_neko_punch",
                "N/A",
                ("Kuro (identidad pública accidental; planificación aprobada)",),
            ),
        )

        result, _ = self.run_message(
            "Quien es Kuro?",
            candidates=candidates,
        )

        self.assertEqual(1, len(result.references))
        self.assertEqual(
            "char-na-maid-gata",
            result.references[0].resolved_entity_id,
        )
    def test_reference_resolution_is_isolated_by_universe(self) -> None:
        candidates = (EntityCandidate("kuro_one", "one_neko_punch", "Kuro"), EntityCandidate("kuro_other", "other_world", "Kuro"))
        result, _ = self.run_message("Kuro", candidates=candidates)
        self.assertEqual("kuro_one", result.references[0].resolved_entity_id)

    def test_message_without_required_universe_requests_clarification(self) -> None:
        result = self.brain.process(BrainRequest("Quien es Kuro?", "u1", "c1", None))
        self.assertTrue(result.ambiguity)
        self.assertEqual("universe_required", result.clarification)
        self.assertEqual(Route.CLARIFICATION, self.router.decide(result).route)

    def test_state_keeps_chapter_and_mode_when_not_changing_universe(self) -> None:
        self.run_message("Ayuda")
        self.assertEqual("chapter_1", self.state.chapter_id)
        self.assertEqual("draft", self.state.mode)

    def test_unknown_message_does_not_call_provider(self) -> None:
        _, decision = self.run_message("zzzxq")
        self.assertEqual(Route.CLARIFICATION, decision.route)
        self.assertFalse(decision.requires_llm)
        self.assertFalse(decision.requires_agent)


if __name__ == "__main__":
    unittest.main()
