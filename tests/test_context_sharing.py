from __future__ import annotations

import unittest
from types import SimpleNamespace

from bot_ia.context import TokenBudget
from bot_ia.contracts import Confidence
from bot_ia.core.context_sharing import build_shared_context
from bot_ia.librarian.models import Coverage, CoverageStatus, EvidencePack, Fragment, RetrievalQuery


class ContextSharingTests(unittest.TestCase):
    def make_execution(self):
        query = RetrievalQuery("¿Quién es Kuro?", "one_neko_punch")
        evidence = EvidencePack(
            query,
            (),
            (
                Fragment("kuro.md", "one_neko_punch", 0, 10, 14, "Kuro es la protagonista.", 1.0, "Personaje"),
            ),
            (),
            (),
            (),
            Confidence.HIGH,
            (("kuro.md", "version-1"),),
            Coverage(CoverageStatus.ESTABLISHED, 1, 1, 0),
        )
        return SimpleNamespace(evidence=evidence, context=SimpleNamespace(text="contexto local"))

    def test_only_retrieved_evidence_is_shared(self):
        shared = build_shared_context(self.make_execution())
        self.assertIn("kuro.md", shared.text)
        self.assertIn("Kuro es la protagonista.", shared.text)
        self.assertIn("No constituye una autorización", shared.text)
        self.assertEqual(shared.universe_id, "one_neko_punch")

    def test_context_is_capped(self):
        execution = self.make_execution()
        shared = build_shared_context(execution, max_chars=1000)
        self.assertLessEqual(len(shared.text), 1100)
        self.assertIn("BOT-IA — CONTEXTO COMPARTIDO", shared.text)

    def test_no_evidence_does_not_fabricate(self):
        query = RetrievalQuery("pregunta sin evidencia", "one_neko_punch")
        evidence = EvidencePack(
            query, (), (), (), (), ("no_match",), Confidence.NONE, (),
            Coverage(CoverageStatus.NO_ENCONTRADO, 0, 0, 0),
        )
        shared = build_shared_context(SimpleNamespace(evidence=evidence))
        self.assertIn("(sin fuentes coincidentes)", shared.text)
        self.assertNotIn("información inventada", shared.text)


if __name__ == "__main__":
    unittest.main()
