from pathlib import Path
import tempfile
import unittest

from bot_ia.agents import AgentRequest, IAChanAgent, IAChanOutputContract, ResponseType, RuleCheck
from bot_ia.context import ContextBuilder, TokenBudget
from bot_ia.contracts import AuthorityLevel, CanonStatus, Confidence, SourceStatus
from bot_ia.librarian import LocalLibrarian, RetrievalQuery, SourceInventory, SourceMetadata, SourceType


class OutputContractTests(unittest.TestCase):
    def contract(self, **changes: object) -> IAChanOutputContract:
        values: dict[str, object] = {
            "response_type": ResponseType.FACTUAL,
            "answer": "Kuro protege la ciudad.",
            "certainty": Confidence.HIGH,
            "interpretation": "Pregunta factual.",
            "used_evidence": ("chapter_01",),
            "evidence_sufficient": True,
            "used_memory": (),
            "memory_authorized": False,
            "universe_id": "one_neko_punch",
            "expected_universe_id": "one_neko_punch",
            "needs_clarification": False,
            "proposed_action": "answer_with_evidence",
            "rule_checks": (RuleCheck("security_no_invention", True, "evidence supplied"),),
        }
        values.update(changes)
        return IAChanOutputContract(**values)  # type: ignore[arg-type]

    def test_factual_response_with_evidence_is_valid(self) -> None:
        self.assertTrue(self.contract().validate().valid)

    def test_factual_without_sufficient_evidence_is_rejected(self) -> None:
        result = self.contract(used_evidence=(), evidence_sufficient=False, certainty=Confidence.LOW, uncertainty="not_established").validate()
        self.assertIn("factual_evidence_insufficient", result.issues)

    def test_opinion_is_identified_without_evidence(self) -> None:
        self.assertTrue(self.contract(response_type=ResponseType.OPINION, used_evidence=(), evidence_sufficient=False).validate().valid)

    def test_proposal_is_identified_without_becoming_fact(self) -> None:
        self.assertTrue(self.contract(response_type=ResponseType.PROPOSAL, used_evidence=(), evidence_sufficient=False).validate().valid)

    def test_uncertainty_is_explicit_when_factual_evidence_is_missing(self) -> None:
        result = self.contract(used_evidence=(), evidence_sufficient=False, certainty=Confidence.HIGH).validate()
        self.assertIn("uncertainty_not_explicit", result.issues)

    def test_authorized_memory_is_allowed(self) -> None:
        self.assertTrue(self.contract(used_memory=("memory:m1",), memory_authorized=True).validate().valid)

    def test_unauthorized_memory_is_rejected(self) -> None:
        self.assertIn("memory_not_authorized", self.contract(used_memory=("memory:m1",), memory_authorized=False).validate().issues)

    def test_wrong_universe_is_rejected(self) -> None:
        self.assertIn("universe_mismatch", self.contract(universe_id="other_world").validate().issues)

    def test_clarification_requirement_is_represented(self) -> None:
        result = self.contract(response_type=ResponseType.CLARIFICATION, needs_clarification=True, proposed_action="ask", used_evidence=(), evidence_sufficient=False)
        self.assertTrue(result.validate().valid)

    def test_failed_rule_check_is_reported(self) -> None:
        result = self.contract(rule_checks=(RuleCheck("universe_isolation", False, "mismatch"),)).validate()
        self.assertIn("rule_check_failed:universe_isolation", result.issues)

    def test_ia_chan_attaches_a_verifiable_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "chapter.md").write_text("Kuro protege la ciudad.", encoding="utf-8")
            metadata = {"chapter.md": SourceMetadata("chapter", SourceType.CHAPTER, AuthorityLevel.PRIMARY, SourceStatus.VALIDATED, CanonStatus.CANON)}
            evidence = LocalLibrarian().retrieve(RetrievalQuery("Kuro", "one_neko_punch"), SourceInventory(root).discover("one_neko_punch", metadata))
            context = ContextBuilder().build(evidence, TokenBudget(100))
            result = IAChanAgent().run(AgentRequest("ia_chan", "one_neko_punch", "creative_writing", "Tengo una idea", None, context, evidence))
        self.assertIsNotNone(result.output_contract)
        self.assertTrue(result.output_contract.validate().valid)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
