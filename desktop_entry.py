# -*- coding: utf-8 -*-
"""Entry point del Core de escritorio de Café Otaku.

Conserva los workers de Telegram y WebChat para el empaquetado, pero la ventana
principal es exclusivamente la interfaz Qt de src/gui.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from bot_ia.config.dotenv import load_dotenv


def _log_path() -> Path:
    work = ROOT / "work"
    work.mkdir(parents=True, exist_ok=True)
    return work / "telegram.log"


def _telegram_log(message: str) -> None:
    with _log_path().open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def _run_telegram_worker() -> int:
    from bot_ia.interfaces.telegram import TelegramApiClient, TelegramPoller
    from bot_ia.interfaces.telegram_outbox import TelegramOutboxStore
    from bot_ia.interfaces.telegram_projects import TelegramProjectsAdapter
    from bot_ia.runtime import build_runtime

    load_dotenv(ROOT / ".env")
    runtime = None
    try:
        runtime = build_runtime(ROOT)
        universe_id = os.getenv("BOT_IA_UNIVERSE", "one_neko_punch")
        provider_id = os.getenv("BOT_IA_PROVIDER", "openai")
        application = runtime.build_application(
            default_universe_id=universe_id,
            provider_id=provider_id,
        )
        client = TelegramApiClient.from_environment()
        if not client.smoke_test():
            raise RuntimeError("Telegram getMe check failed")

        outbox_store = TelegramOutboxStore(runtime.memory_store.path)
        _telegram_log(
            "Telegram: conexión OK; polling iniciado con outbox durable."
        )
        result = TelegramPoller(
            client,
            TelegramProjectsAdapter(application, runtime),
            logger=_telegram_log,
            outbox_store=outbox_store,
        ).run()
        _telegram_log(
            "Telegram: detenido "
            f"polls={result.polls} "
            f"received={result.updates_received} "
            f"processed={result.updates_processed} "
            f"sent={result.responses_sent} "
            f"errors={result.transport_errors}"
        )
        return 0
    except Exception as error:
        _telegram_log(
            f"Telegram ERROR: {type(error).__name__}: {error}"
        )
        _telegram_log(traceback.format_exc())
        return 1
    finally:
        if runtime is not None:
            runtime.memory_store.close()


def _run_web_chat_worker() -> int:
    from bot_ia.interfaces.web_chat import run_web_chat_server
    from bot_ia.runtime import build_runtime

    load_dotenv(ROOT / ".env")
    runtime = None
    try:
        host = os.getenv("BOT_IA_HOST", "127.0.0.1")
        port = int(os.getenv("BOT_IA_PORT", "8787"))
        token = os.getenv("BOT_IA_API_TOKEN", "").strip() or None
        insecure_lan = (
            os.getenv("BOT_IA_ALLOW_INSECURE_LAN", "")
            .strip()
            .lower()
            in {"1", "true", "yes", "on"}
        )
        public_base_url = os.getenv(
            "BOT_IA_PUBLIC_BASE_URL",
            "",
        ).strip()
        if host not in {"127.0.0.1", "localhost", "::1"}:
            if len(token or "") < 32:
                raise RuntimeError(
                    "BOT_IA_API_TOKEN must contain at least 32 characters "
                    "for LAN web chat"
                )
            if (
                not insecure_lan
                and not public_base_url.lower().startswith("https://")
            ):
                raise RuntimeError(
                    "non-local web chat requires HTTPS unless "
                    "BOT_IA_ALLOW_INSECURE_LAN=true is explicitly enabled"
                )

        allow_external_api = (
            os.getenv("BOT_IA_ALLOW_REMOTE_EXTERNAL_API", "")
            .strip()
            .lower()
            in {"1", "true", "yes", "on"}
        )
        runtime = build_runtime(ROOT)
        universe_id = os.getenv(
            "BOT_IA_UNIVERSE",
            "one_neko_punch",
        )
        provider_id = os.getenv(
            "BOT_IA_PROVIDER",
            "openai",
        )
        application = runtime.build_application(
            default_universe_id=universe_id,
            provider_id=provider_id,
        )
        run_web_chat_server(
            application,
            host=host,
            port=port,
            api_token=token,
            allow_external_api=allow_external_api,
        )
        return 0
    except Exception as error:
        _log_path()
        _telegram_log(
            f"WebChat ERROR: {type(error).__name__}: {error}"
        )
        _telegram_log(traceback.format_exc())
        return 1
    finally:
        if runtime is not None:
            runtime.memory_store.close()


def main() -> int:
    if "--telegram-worker" in sys.argv:
        return _run_telegram_worker()
    if "--web-chat-worker" in sys.argv:
        return _run_web_chat_worker()

    from gui.app import main as qt_main

    return qt_main()


if __name__ == "__main__":
    raise SystemExit(main())
