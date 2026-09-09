from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from bot_ia.agents import AgentRegistry, AgentRequest, AgentStatus, EditorAgent, ExternalReference, HistorianAgent, IAChanAgent, ResearcherAgent
from bot_ia.context import ContextBuilder, TokenBudget
from bot_ia.contracts import AuthorityLevel, CanonStatus, Confidence, SourceStatus, UniverseDefinition, UniverseRegistry
from bot_ia.core import BrainRequest, Intent, LocalBrain, Router
from bot_ia.librarian import LocalLibrarian, RetrievalQuery, SourceInventory, SourceMetadata, SourceType, SpoilerLevel, SpoilerScope, TemporalScope
from bot_ia.librarian.models import EvidenceConflict


class Phase5Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "chapter.md").write_text("Kuro protege la ciudad.", encoding="utf-8")
        (root / "plan.md").write_text("Kuro viajara al norte.", encoding="utf-8")
        metadata = {
            "chapter.md": SourceMetadata("chapter", SourceType.CHAPTER, AuthorityLevel.PRIMARY, SourceStatus.VALIDATED, CanonStatus.CANON),
            "plan.md": SourceMetadata("plan", SourceType.PLANNING, AuthorityLevel.PLAN, SourceStatus.VALIDATED, CanonStatus.PLANNING),
        }
        entries = SourceInventory(root).discover("one_neko_punch", metadata)
        self.evidence = LocalLibrarian().retrieve(RetrievalQuery("Kuro", "one_neko_punch"), entries)
        self.context = ContextBuilder().build(self.evidence, TokenBudget(100), future_task=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def request(self, agent_id: str, **changes: object) -> AgentRequest:
        values: dict[str, object] = {"agent_id": agent_id, "universe_id": "one_neko_punch", "intent": "creative_writing", "user_request": "Help with this brief", "state": None, "context_pack": self.context, "evidence_pack": self.evidence}
        values.update(changes)
        return AgentRequest(**values)  # type: ignore[arg-type]

    def test_ia_chan_receives_prepared_context(self) -> None:
        result = IAChanAgent().run(self.request("ia_chan", constraints=("keep tone warm",)))
        self.assertEqual(AgentStatus.COMPLETE, result.status)
        self.assertEqual("context_received", result.findings[0].category)

    def test_historian_distinguishes_shown_and_planned(self) -> None:
        result = HistorianAgent().run(self.request("historian", intent="continuity"))
        self.assertIn("chapter", result.findings[0].value)
        self.assertIn("plan", result.findings[1].value)

    def test_historian_preserves_conflict(self) -> None:
        conflict_evidence = replace(self.evidence, conflicts=(EvidenceConflict("kuro", ("chapter", "plan"), "test"),))
        result = HistorianAgent().run(self.request("historian", evidence_pack=conflict_evidence))
        self.assertIn("kuro", result.conflicts)
        self.assertEqual("conflict", result.uncertainty)

    def test_editor_receives_style_constraints_without_rewrite(self) -> None:
        result = EditorAgent().run(self.request("editor", constraints=("POV: third person", "past tense")))
        self.assertEqual(2, len(result.findings))
        self.assertIn("no rewrite", result.answer.lower())

    def test_researcher_keeps_external_reference_separate(self) -> None:
        reference = ExternalReference("OPM guide", "wiki", "v1", date(2026, 1, 1), Confidence.MEDIUM, SpoilerScope(SpoilerLevel.LOW), "comparison only")
        result = ResearcherAgent().run(self.request("researcher", external_references=(reference,)))
        self.assertEqual("external_reference", result.findings[0].category)
        self.assertEqual("external_references_not_canon", result.uncertainty)

    def test_agents_do_not_mutate_context_or_canon(self) -> None:
        before = self.evidence
        IAChanAgent().run(self.request("ia_chan"))
        HistorianAgent().run(self.request("historian"))
        self.assertEqual(before, self.evidence)

    def test_agents_reject_cross_universe_context(self) -> None:
        result = IAChanAgent().run(self.request("ia_chan", universe_id="other_world"))
        self.assertEqual(AgentStatus.REJECTED, result.status)
        self.assertEqual("context_universe_mismatch", result.uncertainty)

    def test_contracts_are_json_serializable(self) -> None:
        request = self.request("ia_chan")
        result = IAChanAgent().run(request)
        json.dumps(request.to_dict())
        json.dumps(result.to_dict())

    def test_registry_maps_and_dispatches_agents(self) -> None:
        registry = AgentRegistry()
        self.assertEqual("ia_chan", registry.agent_for_intent(Intent.CREATIVE_WRITING))
        self.assertEqual("editor", registry.agent_for_intent(Intent.EDITORIAL_REVIEW))
        self.assertEqual(AgentStatus.COMPLETE, registry.dispatch(self.request("ia_chan")).status)

    def test_router_decision_identifies_ia_chan(self) -> None:
        universes = UniverseRegistry()
        universes.register(UniverseDefinition("one_neko_punch", "One Neko Punch", Path("data/one")))
        result = LocalBrain(universes).process(BrainRequest("Escribe una escena", "user", "conversation", None, "one_neko_punch"))
        self.assertEqual("ia_chan", Router().decide(result).agent_id)


if __name__ == "__main__":
    unittest.main()
