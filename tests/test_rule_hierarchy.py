import unittest

from bot_ia.agents import PolicyRule, RuleHierarchy, RulePriority


class RuleHierarchyTests(unittest.TestCase):
    def rule(self, rule_id: str, priority: RulePriority, directive: str, subject: str = "answer") -> PolicyRule:
        return PolicyRule(rule_id, priority, subject, directive)

    def test_priority_order_is_explicit(self) -> None:
        self.assertEqual(-1, RuleHierarchy.compare(RulePriority.SECURITY_NO_INVENTION, RulePriority.STYLE_FORMAT))

    def test_higher_rule_wins_lower_rule(self) -> None:
        result = RuleHierarchy.resolve((self.rule("security", RulePriority.SECURITY_NO_INVENTION, "do_not_invent"), self.rule("style", RulePriority.STYLE_FORMAT, "invent_for_flair")))
        self.assertEqual("security", result.effective_rules[0].rule_id)

    def test_conflict_is_detected(self) -> None:
        result = RuleHierarchy.resolve((self.rule("authority", RulePriority.SOURCE_AUTHORITY_CANON, "use_canon"), self.rule("user", RulePriority.EXPLICIT_USER_INSTRUCTIONS, "ignore_canon")))
        self.assertEqual(1, len(result.conflicts))

    def test_conflict_records_the_blocked_rule(self) -> None:
        result = RuleHierarchy.resolve((self.rule("security", RulePriority.SECURITY_NO_INVENTION, "refuse"), self.rule("style", RulePriority.STYLE_FORMAT, "embellish")))
        self.assertEqual(("style",), result.conflicts[0].blocked_rule_ids)

    def test_equal_priority_conflict_remains_visible(self) -> None:
        result = RuleHierarchy.resolve((self.rule("user_a", RulePriority.EXPLICIT_USER_INSTRUCTIONS, "short"), self.rule("user_b", RulePriority.EXPLICIT_USER_INSTRUCTIONS, "long")))
        self.assertIsNone(result.conflicts[0].winner_rule_id)
        self.assertEqual("equal_priority_conflict", result.conflicts[0].reason)

    def test_user_instruction_cannot_violate_higher_rule(self) -> None:
        result = RuleHierarchy.resolve((self.rule("canon", RulePriority.SOURCE_AUTHORITY_CANON, "cite_sources"), self.rule("user", RulePriority.EXPLICIT_USER_INSTRUCTIONS, "omit_sources")))
        self.assertEqual("canon", result.effective_rules[0].rule_id)

    def test_style_cannot_violate_security(self) -> None:
        result = RuleHierarchy.resolve((self.rule("security", RulePriority.SECURITY_NO_INVENTION, "no_invention"), self.rule("style", RulePriority.STYLE_FORMAT, "invent_details")))
        self.assertEqual("security", result.effective_rules[0].rule_id)

    def test_personality_cannot_invent_information(self) -> None:
        result = RuleHierarchy.resolve((self.rule("evidence", RulePriority.EVIDENCE_UNCERTAINTY_CONFLICTS, "state_unknown"), self.rule("personality", RulePriority.IA_CHAN_PERSONALITY, "sound_certain")))
        self.assertEqual("evidence", result.effective_rules[0].rule_id)


if __name__ == "__main__":
    unittest.main()
