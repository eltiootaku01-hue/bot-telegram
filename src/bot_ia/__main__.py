from __future__ import annotations

import os
from pathlib import Path

from bot_ia.core.application import ApplicationRequest
from bot_ia.runtime import build_runtime


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    universe_id = os.getenv("BOT_IA_UNIVERSE", "one_neko_punch")
    provider_id = os.getenv("BOT_IA_PROVIDER", "ollama")

    runtime = build_runtime(project_root)
    runtime.registry.provider(provider_id)

    app = runtime.build_application(
        default_universe_id=universe_id,
        provider_id=provider_id,
    )

    print("BOT-IA iniciado.")
    print("Universo:", universe_id)
    print("Proveedor:", provider_id)
    print("Escribe 'salir' para terminar.")
    print()

    try:
        while True:
            message = input("> ").strip()

            if message.lower() in {"salir", "exit", "quit"}:
                print("BOT-IA finalizado.")
                break

            if not message:
                continue

            response = app.handle(
                ApplicationRequest(
                    user_id="console-user",
                    conversation_id="console-session",
                    message=message,
                )
            )

            print()
            print(response.text)
            print()
    finally:
        runtime.memory_store.close()


if __name__ == "__main__":
    main()
