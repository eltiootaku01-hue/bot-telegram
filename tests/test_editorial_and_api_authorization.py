import unittest

from bot_ia.contracts import Confidence
from bot_ia.core.application import BotApplication, ApplicationRequest, InMemorySessionStore
from bot_ia.core.models import BrainResult, Intent, NormalizedMessage, Route
from bot_ia.core.router import Router


class EditorialAndApiAuthorizationTests(unittest.TestCase):
    def _brain(self, intent: Intent) -> BrainResult:
        return BrainResult(
            NormalizedMessage("revisa este capítulo", "revisa este capítulo", ("revisa", "este", "capítulo")),
            intent,
            Confidence.HIGH,
            "one_neko_punch",
            (),
            False,
            None,
            None,
            "active",
        )

    def test_editorial_review_is_executable_by_writing_provider(self):
        decision = Router().decide(self._brain(Intent.EDITORIAL_REVIEW))
        self.assertIs(decision.route, Route.LLM)
        self.assertTrue(decision.requires_agent)
        self.assertTrue(decision.requires_llm)
        self.assertEqual(decision.agent_id, "editor")

    def test_factual_requests_remain_search_by_default(self):
        decision = Router().decide(self._brain(Intent.FACTUAL))
        self.assertIs(decision.route, Route.SEARCH)
        self.assertTrue(decision.requires_search)
        self.assertFalse(decision.requires_llm)
        self.assertFalse(decision.external_api_authorized)

    def test_explicit_api_authorization_preserves_local_search(self):
        class StubBrain:
            def process(self, request):
                return self._result

        stub_brain = StubBrain()
        stub_brain._result = self._brain(Intent.FACTUAL)
        app = BotApplication(stub_brain, Router(), InMemorySessionStore(), default_universe_id="one_neko_punch")
        response = app.handle(
            ApplicationRequest(
                "user",
                "conversation",
                "¿Quién es Saitama?",
                allow_external_api=True,
            )
        )

        self.assertIs(response.decision.route, Route.LLM)
        self.assertTrue(response.decision.requires_search)
        self.assertTrue(response.decision.requires_llm)
        self.assertTrue(response.decision.external_api_authorized)
        self.assertIn("local evidence remains required", response.decision.reason)


if __name__ == "__main__":
    unittest.main()
