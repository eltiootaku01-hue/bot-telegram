# -*- coding: utf-8 -*-
"""Document-only structural checks for the BOT-IA personality contract."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "PERSONALITY_CONTRACT_V1.md"


class PersonalityContractDocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = CONTRACT.read_text(encoding="utf-8")

    def test_all_six_personalities_are_documented(self):
        for heading in (
            "Cari — anfitriona social",
            "Cami — guardiana de seguridad",
            "Sunna — guardiana del conocimiento",
            "Chie — juegos y progreso",
            "Chloe — pedidos ordinarios",
            "Scarlet — solicitudes especiales",
        ):
            with self.subTest(personality=heading):
                self.assertIn(heading, self.document)

    def test_central_safety_and_single_spokesperson_rules_are_documented(self):
        required_phrases = (
            "como máximo una respuesta pública coordinada",
            "la política central",
            "modo de observación",
            "contextos separados",
            "adaptador de Discord",
            "flujos activos de Telegram",
            "QWebEngine",
        )
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.casefold(), self.document.casefold())

    def test_all_acceptance_scenarios_are_present(self):
        for number in range(1, 13):
            scenario_id = f"PC-{number:02d}"
            with self.subTest(scenario=scenario_id):
                self.assertIn(f"| {scenario_id} |", self.document)

    def test_chloe_scarlet_split_is_marked_pending(self):
        self.assertIn("Decisión abierta", self.document)
        self.assertIn("pendiente de validación", self.document)

    def test_scenarios_are_not_misrepresented_as_executed(self):
        self.assertIn("no ejecutados", self.document)
        self.assertIn(
            "No deben marcarse como aprobados hasta que existan pruebas ejecutadas",
            self.document,
        )


if __name__ == "__main__":
    unittest.main()
