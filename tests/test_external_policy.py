import unittest

from bot_ia.contracts import Confidence
from bot_ia.core.external_policy import external_proposal_prefix, wrap_external_proposal
from bot_ia.agents.output_contract import IAChanOutputContract, ResponseType


class ExternalPolicyTests(unittest.TestCase):
    def test_external_output_is_explicitly_marked(self):
        result = wrap_external_proposal("Saitama es un héroe de clase A.")
        self.assertTrue(result.startswith(external_proposal_prefix()))
        self.assertIn("no incorporada al canon", result)
        self.assertIn("Saitama es un héroe", result)

    def test_empty_external_output_still_has_marker(self):
        self.assertEqual(external_proposal_prefix(), wrap_external_proposal("   "))

    def test_proposal_does_not_require_evidence(self):
        contract = IAChanOutputContract(
            ResponseType.PROPOSAL,
            wrap_external_proposal("Dato externo para revisar."),
            Confidence.LOW,
            "proposal; external; unverified",
            (),
            False,
            (),
            True,
            "one_neko_punch",
            "one_neko_punch",
            False,
            "review_before_library_incorporation",
            "external_api_unverified",
        )
        validation = contract.validate()
        self.assertTrue(validation.valid, validation.issues)


if __name__ == "__main__":
    unittest.main()
