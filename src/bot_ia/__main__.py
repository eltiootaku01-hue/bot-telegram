# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path

from bot_ia.config.dotenv import load_dotenv
from bot_ia.core.application import ApplicationRequest
from bot_ia.interfaces.telegram import TelegramApiClient, TelegramPoller
from bot_ia.interfaces.telegram_outbox import TelegramOutboxStore
from bot_ia.interfaces.telegram_projects import TelegramProjectsAdapter
from bot_ia.interfaces.web import run_web_server
from bot_ia.interfaces.web_chat import run_web_chat_server
from bot_ia.runtime import build_runtime

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_private_or_loopback_host(host: str) -> bool:
    if host in _LOCAL_HOSTS:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BOT-IA Knowledge Engine")
    parser.add_argument("--mode", choices=("console", "telegram", "web", "web-chat"), default="console")
    parser.add_argument("--host", default=os.getenv("BOT_IA_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("BOT_IA_PORT", "8787")))
    return parser


def _build_application(project_root: Path):
    universe_id = os.getenv("BOT_IA_UNIVERSE", "one_neko_punch")
    provider_id = os.getenv("BOT_IA_PROVIDER", "openai")
    runtime = build_runtime(project_root)
    runtime.registry.provider(provider_id)
    application = runtime.build_application(default_universe_id=universe_id, provider_id=provider_id)
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
        response = application.handle(ApplicationRequest("console-user", "console-session", message))
        print()
        print(response.text)
        print()


def _run_telegram(application, runtime) -> None:
    client = TelegramApiClient.from_environment()
    if not client.smoke_test():
        raise RuntimeError("Telegram getMe check failed")
    outbox_store = TelegramOutboxStore(runtime.memory_store.path)
    result = TelegramPoller(
        client,
        TelegramProjectsAdapter(application, runtime),
        outbox_store=outbox_store,
    ).run()
    print("Telegram detenido:", f"polls={result.polls}", f"received={result.updates_received}", f"processed={result.updates_processed}", f"sent={result.responses_sent}", f"errors={result.transport_errors}")


def _web_security(project_root: Path, host: str) -> tuple[str | None, bool]:
    token = os.getenv("BOT_IA_API_TOKEN")
    allow_external_api = _env_bool("BOT_IA_ALLOW_REMOTE_EXTERNAL_API", False)
    if host not in _LOCAL_HOSTS:
        if not token:
            raise RuntimeError("BOT_IA_API_TOKEN is required when the web API is not bound to localhost")
        if len(token) < 32:
            raise RuntimeError("BOT_IA_API_TOKEN must contain at least 32 characters for non-local web API")
        public_base_url = os.getenv("BOT_IA_PUBLIC_BASE_URL", "")
        allow_insecure_lan = _env_bool("BOT_IA_ALLOW_INSECURE_LAN", False)
        if not public_base_url.lower().startswith("https://") and not (allow_insecure_lan and _is_private_or_loopback_host(host)):
            raise RuntimeError("BOT_IA_PUBLIC_BASE_URL must be HTTPS for remote web API; for a trusted private LAN you may explicitly set BOT_IA_ALLOW_INSECURE_LAN=true")
    else:
        public_base_url = os.getenv("BOT_IA_PUBLIC_BASE_URL")
    return public_base_url, allow_external_api


def _run_web(application, host: str, port: int) -> None:
    public_base_url, allow_external_api = _web_security(Path.cwd(), host)
    run_web_server(
        application,
        host=host,
        port=port,
        api_token=os.getenv("BOT_IA_API_TOKEN"),
        allow_external_api=allow_external_api,
        public_base_url=public_base_url,
    )


def _run_web_chat(application, host: str, port: int) -> None:
    _public_base_url, allow_external_api = _web_security(Path.cwd(), host)
    run_web_chat_server(
        application,
        host=host,
        port=port,
        api_token=os.getenv("BOT_IA_API_TOKEN"),
        allow_external_api=allow_external_api,
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
            _run_telegram(application, runtime)
        elif args.mode == "web":
            _run_web(application, args.host, args.port)
        else:
            _run_web_chat(application, args.host, args.port)
    finally:
        runtime.memory_store.close()


if __name__ == "__main__":
    main()
