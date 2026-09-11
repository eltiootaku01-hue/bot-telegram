import unittest
from types import SimpleNamespace

from bot_ia.core.local_workflow import LocalWorkflow
from bot_ia.providers.models import ProviderResponse, ProviderStatus, ProviderUsage


class _ProviderManager:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, decision, request, *, fallback_provider=None):
        self.calls += 1
        response = ProviderResponse(
            provider=request.provider,
            model=request.model,
            status=ProviderStatus.SUCCESS,
            output_text=f"response-{self.calls}",
            usage=ProviderUsage(),
            latency_ms=0,
            request_id=f"request-{self.calls}",
        )
        return SimpleNamespace(response=response)


class ProviderResponseCacheScopeTests(unittest.TestCase):
    def _workflow(self):
        manager = _ProviderManager()
        workflow = LocalWorkflow(
            {},
            provider_manager=manager,
            provider_id="test",
            provider_model="test-model",
        )
        return workflow, manager

    def _inputs(self, *, agent_id="ia_chan", universe_id="test_universe", authorized=False):
        decision = SimpleNamespace(
            requires_llm=True,
            external_api_authorized=authorized,
            reason="test",
        )
        brain = SimpleNamespace(
            universe_id=universe_id,
            intent=SimpleNamespace(value="creative"),
            normalized=SimpleNamespace(normalized="same query", original="same query"),
        )
        agent = SimpleNamespace(
            agent_id=agent_id,
            recommendation=f"guidance for {agent_id}",
            uncertainty=None,
            conflicts=(),
        )
        context = SimpleNamespace(text="same context")
        return decision, brain, agent, context

    def test_same_query_context_different_agents_do_not_share_cache(self):
        workflow, manager = self._workflow()
        workflow._run_local_provider(*self._inputs(agent_id="ia_chan"))
        workflow._run_local_provider(*self._inputs(agent_id="editor"))
        self.assertEqual(2, manager.calls)

    def test_same_query_context_different_universes_do_not_share_cache(self):
        workflow, manager = self._workflow()
        workflow._run_local_provider(*self._inputs(universe_id="one_neko_punch"))
        second = workflow._run_local_provider(*self._inputs(universe_id="fragmentado"))
        self.assertEqual(2, manager.calls)
        self.assertEqual("response-2", second.output_text)

    def test_same_agent_query_context_reuses_cache(self):
        workflow, manager = self._workflow()
        inputs = self._inputs()
        first = workflow._run_local_provider(*inputs)
        second = workflow._run_local_provider(*inputs)
        self.assertEqual(1, manager.calls)
        self.assertEqual("response-1", first.output_text)
        self.assertTrue(second.request_id.startswith("cache:"))


if __name__ == "__main__":
    unittest.main()
