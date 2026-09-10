from __future__ import annotations

import argparse
import os
from pathlib import Path

from bot_ia.config.dotenv import load_dotenv
from bot_ia.core.application import ApplicationRequest
from bot_ia.interfaces.telegram import TelegramAdapter, TelegramApiClient, TelegramPoller
from bot_ia.interfaces.web import run_web_server
from bot_ia.runtime import build_runtime


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BOT-IA Knowledge Engine")
    parser.add_argument(
        "--mode",
        choices=("console", "telegram", "web"),
        default="console",
        help="interface to run (default: console)",
    )
    parser.add_argument("--host", default=os.getenv("BOT_IA_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("BOT_IA_PORT", "8787")))
    return parser


def _build_application(project_root: Path):
    universe_id = os.getenv("BOT_IA_UNIVERSE", "one_neko_punch")
    provider_id = os.getenv("BOT_IA_PROVIDER", "gemini")
    runtime = build_runtime(project_root)
    runtime.registry.provider(provider_id)
    application = runtime.build_application(
        default_universe_id=universe_id,
        provider_id=provider_id,
    )
    return runtime, application, universe_id, provider_id


def _run_console(application, universe_id: str, provider_id: str) -> None:
    print("BOT-IA iniciado.")
    print("Universo:", universe_id)
    print("Proveedor:", provider_id)
    print("Escribe 'salir' para terminar.")
    print()
    while True:
        message = input("> ").strip()
        if message.lower() in {"salir", "exit", "quit"}:
            print("BOT-IA finalizado.")
            return
        if not message:
            continue
        response = application.handle(
            ApplicationRequest("console-user", "console-session", message)
        )
        print()
        print(response.text)
        print()


def _run_telegram(application) -> None:
    client = TelegramApiClient.from_environment()
    if not client.smoke_test():
        raise RuntimeError("Telegram getMe check failed")
    adapter = TelegramAdapter(application)
    poller = TelegramPoller(client, adapter)
    print("BOT-IA Telegram iniciado. Ctrl+C para detenerlo.")
    result = poller.run()
    print(
        "Telegram detenido:",
        f"polls={result.polls}",
        f"received={result.updates_received}",
        f"processed={result.updates_processed}",
        f"sent={result.responses_sent}",
        f"errors={result.transport_errors}",
    )


def _run_web(application, host: str, port: int) -> None:
    token = os.getenv("BOT_IA_API_TOKEN")
    if host not in {"127.0.0.1", "localhost", "::1"} and not token:
        raise RuntimeError(
            "BOT_IA_API_TOKEN is required when the web API is not bound to localhost"
        )
    run_web_server(
        application,
        host=host,
        port=port,
        api_token=token,
        public_base_url=os.getenv("BOT_IA_PUBLIC_BASE_URL"),
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")
    args = _parser().parse_args()
    runtime, application, universe_id, provider_id = _build_application(project_root)
    try:
        if args.mode == "console":
            _run_console(application, universe_id, provider_id)
        elif args.mode == "telegram":
            _run_telegram(application)
        else:
            _run_web(application, args.host, args.port)
    finally:
        runtime.memory_store.close()


if __name__ == "__main__":
    main()
