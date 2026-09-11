import unittest

from bot_ia.memory.retrieval_policy import (
    DEFAULT_CANDIDATE_BUDGET,
    MAX_CANDIDATE_BUDGET,
    candidate_budget,
)


class RetrievalPolicyTests(unittest.TestCase):
    def test_default_budget_is_bounded(self):
        self.assertEqual(candidate_budget(), DEFAULT_CANDIDATE_BUDGET)
        self.assertLessEqual(DEFAULT_CANDIDATE_BUDGET, MAX_CANDIDATE_BUDGET)

    def test_requested_budget_is_capped(self):
        self.assertEqual(candidate_budget(MAX_CANDIDATE_BUDGET + 100), MAX_CANDIDATE_BUDGET)

    def test_invalid_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            candidate_budget(0)


if __name__ == "__main__":
    unittest.main()
