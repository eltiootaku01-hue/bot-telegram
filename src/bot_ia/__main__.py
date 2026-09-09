from pathlib import Path

from bot_ia.core.application import ApplicationRequest
from bot_ia.runtime import build_runtime


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]

    runtime = build_runtime(
        project_root,
        key_loader=lambda _: None,
    )

    app = runtime.build_application(
        default_universe_id="one_neko_punch",
        provider_id="ollama",
    )

    print("BOT-IA iniciado.")
    print("Universo:", "one_neko_punch")
    print("Escribe 'salir' para terminar.")
    print()

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


if __name__ == "__main__":
    main()