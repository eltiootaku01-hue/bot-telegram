from __future__ import annotations

import hashlib
import json
import unittest
from types import SimpleNamespace

from bot_ia.contracts import Confidence
from bot_ia.core.context_sharing import ShareScope, build_shared_context
from bot_ia.librarian.models import Coverage, CoverageStatus, EvidencePack, Fragment, RetrievalQuery


class ContextSharingTests(unittest.TestCase):
    def make_execution(self, fragment_text="Kuro es la protagonista."):
        query = RetrievalQuery("¿Quién es Kuro?", "one_neko_punch")
        evidence = EvidencePack(
            query,
            (),
            (
                Fragment("kuro.md", "one_neko_punch", 0, 10, 14, fragment_text, 1.0, "Personaje"),
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
        self.assertIn("No concede acceso a BOT-IA", shared.text)
        self.assertEqual(shared.universe_id, "one_neko_punch")
        self.assertEqual(shared.scope, ShareScope.RELEVANT)

    def test_packet_is_independent_and_has_digest(self):
        shared = build_shared_context(self.make_execution())
        self.assertTrue(shared.packet_id.startswith("ctx-"))
        self.assertEqual(shared.content_sha256, hashlib.sha256(shared.text.encode("utf-8")).hexdigest())
        self.assertNotIn("LocalExecution", shared.text)
        self.assertNotIn("biblioteca/", shared.text)

    def test_packet_can_be_serialized_without_runtime_objects(self):
        shared = build_shared_context(self.make_execution())
        payload = shared.as_payload()
        self.assertEqual(payload["packet_id"], shared.packet_id)
        self.assertEqual(payload["scope"], "relevant")
        self.assertEqual(payload["universe_id"], "one_neko_punch")
        self.assertEqual(payload["source_ids"], ["kuro.md"])
        self.assertNotIn("runtime", json.dumps(payload, ensure_ascii=False).lower())
        self.assertEqual(json.loads(shared.as_json())["content_sha256"], shared.content_sha256)

    def test_external_prompt_is_self_contained_but_has_no_access_instruction(self):
        shared = build_shared_context(self.make_execution())
        prompt = shared.as_external_prompt()
        self.assertIn("Kuro es la protagonista.", prompt)
        self.assertIn("No tienes acceso a BOT-IA", prompt)
        self.assertNotIn("LocalExecution", prompt)

    def test_context_is_capped(self):
        execution = self.make_execution()
        shared = build_shared_context(execution, max_chars=1000)
        self.assertLessEqual(len(shared.text), 1000)
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

    def test_common_api_credentials_are_redacted(self):
        execution = self.make_execution("Texto normal sk-12345678901234567890 y token: abcdefghijklmnop.")
        shared = build_shared_context(execution)
        self.assertNotIn("sk-12345678901234567890", shared.text)
        self.assertNotIn("token: abcdefghijklmnop", shared.text)
        self.assertIn("[DATO SENSIBLE OMITIDO]", shared.text)
        self.assertGreaterEqual(shared.redactions, 2)


if __name__ == "__main__":
    unittest.main()
