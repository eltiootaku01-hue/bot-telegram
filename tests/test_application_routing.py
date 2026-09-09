from __future__ import annotations

import unittest

from bot_ia.contracts import UniverseRegistry
from bot_ia.core import LocalBrain, Router
from bot_ia.core.application import ApplicationRequest, BotApplication, InMemorySessionStore


class ExplodingExecutor:
    def execute(self, *_args, **_kwargs):
        raise AssertionError("deterministic route must not enter workflow executor")


class ApplicationRoutingTests(unittest.TestCase):
    def test_universe_independent_local_request_does_not_require_workflow(self) -> None:
        app = BotApplication(
            LocalBrain(UniverseRegistry()),
            Router(),
            InMemorySessionStore(),
            executor=ExplodingExecutor(),
        )

        response = app.handle(ApplicationRequest("u1", "c1", "Hola."))

        self.assertEqual("Solicitud local procesada.", response.text)
        self.assertIsNone(response.execution)


if __name__ == "__main__":
    unittest.main()
