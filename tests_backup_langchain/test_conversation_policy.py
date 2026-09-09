import unittest
from bot_ia.agents import ConversationAct, ConversationPolicy

class ConversationPolicyTests(unittest.TestCase):
    def setUp(self): self.policy=ConversationPolicy()
    def test_factual(self): self.assertEqual(ConversationAct.FACT, self.policy.assess("¿Quién es Kuro?").act)
    def test_doubt(self): self.assertEqual(ConversationAct.DOUBT, self.policy.assess("¿Yume recuerda eso?").act)
    def test_hypothesis(self): self.assertEqual("hypothesis", self.policy.assess("Quizá Yume lo sabe").epistemic_label)
    def test_idea(self): self.assertEqual(ConversationAct.IDEA, self.policy.assess("Tengo una idea nueva").act)
    def test_proposal(self): self.assertEqual("proposal", self.policy.assess("Kuro podría ser sarcástica").epistemic_label)
    def test_opinion(self): self.assertEqual("opinion", self.policy.assess("¿Qué te parece Kuro?").epistemic_label)
    def test_advice(self): self.assertEqual("recommendation", self.policy.assess("¿Qué me recomiendas?").response_mode)
    def test_probable_sarcasm_is_not_asserted(self): self.assertEqual("ambiguous", self.policy.assess("Claro, seguro").epistemic_label)
    def test_sarcasm_asks(self): self.assertTrue(self.policy.assess("Claro, seguro").requires_clarification)
    def test_ambiguous_reference(self): self.assertTrue(self.policy.assess("¿Ella quién es?").requires_clarification)
    def test_subjective(self): self.assertEqual(ConversationAct.OPINION, self.policy.assess("¿Qué te parece?").act)
    def test_empty_needs_clarification(self): self.assertTrue(self.policy.assess("").requires_clarification)
    def test_no_invention(self): self.assertEqual("not_established", self.policy.assess("¿Qué pasó?").epistemic_label)
    def test_factual_is_local(self): self.assertFalse(self.policy.assess("¿Quién es Kuro?").requires_llm)
    def test_creative_requires_llm(self): self.assertTrue(self.policy.assess("Escribe una escena").requires_llm)
    def test_casual(self): self.assertEqual(ConversationAct.CASUAL, self.policy.assess("Hola, ¿qué tal?").act)
    def test_context_resolves_reference(self): self.assertFalse(self.policy.assess("¿Ella quién es?", ("Hitomi",)).requires_clarification)
    def test_memory_is_not_canon(self): self.assertNotEqual("canon", self.policy.assess("Kuro podría ser sarcástica").epistemic_label)

if __name__ == '__main__': unittest.main()
