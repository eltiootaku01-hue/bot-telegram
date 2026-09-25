# -*- coding: utf-8 -*-
from pathlib import Path
import tempfile
from bot_ia.contracts import UniverseDefinition, UniverseRegistry
from bot_ia.core.application import BotApplication, InMemorySessionStore
from bot_ia.core.brain import LocalBrain
from bot_ia.core.router import Router
from bot_ia.interfaces.telegram import PollingConfig, TelegramAdapter, TelegramApiClient, TelegramPoller
import traceback

def _update(update_id=7, text="Hola"):
    return {"update_id": update_id, "message": {"from": {"id": 1}, "chat": {"id": 2}, "text": text}}

def test_debug_telegram_pipeline():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        reg = UniverseRegistry()
        reg.register(UniverseDefinition("one_neko_punch", "One Neko Punch", root / "data"))
        app = BotApplication(LocalBrain(reg), Router(), InMemorySessionStore(), default_universe_id="one_neko_punch")
        adapter = TelegramAdapter(app)
        try:
            direct = adapter.handle_update(_update()["message"] and _update())
            print("DEBUG_DIRECT", direct)
        except Exception:
            print("DEBUG_DIRECT_EXCEPTION")
            traceback.print_exc()
        logs=[]
        calls=[]
        batches=[[_update()]]
        def transport(url, payload, timeout):
            calls.append((url,payload))
            if url.endswith("getUpdates"):
                return {"ok": True, "result": batches.pop(0)}
            return {"ok": True, "result": {"message_id": 99}}
        client=TelegramApiClient("local-test-token", transport=transport, sleeper=lambda _:None)
        poller=TelegramPoller(client, adapter, config=PollingConfig(max_consecutive_failures=5), sleeper=lambda _:None, logger=logs.append)
        result=poller.run(max_cycles=1)
        print("DEBUG_RESULT", result)
        print("DEBUG_LOGS", logs)
        print("DEBUG_CALLS", calls)
        assert result.responses_sent == 1, (result, logs, calls)
