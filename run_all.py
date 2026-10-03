# -*- coding: utf-8 -*-
import importlib
import multiprocessing
import os
import sys
import uvicorn

# Permitir importaciones relativas desde la raíz
sys.path.append(os.path.abspath(os.path.dirname(__file__)))


STARTUP_ENTRYPOINTS = (
    ("FastAPI", "src.api.main", "app"),
    ("Telegram", "src.bot.main", "create_bot_app"),
    ("Discord", "src.discord.bot", "run_discord_bot"),
)


class StartupPreflightError(RuntimeError):
    """Indica que un entrypoint de Path B no puede cargarse antes del arranque."""


def _preflight_error(
    entrypoint: str,
    module_name: str,
    attribute_name: str,
    exc: Exception,
) -> StartupPreflightError:
    """Construye un error sin exponer secretos ni valores de configuración."""
    if isinstance(exc, ModuleNotFoundError):
        dependency = getattr(exc, "name", None) or module_name
        detail = f"missing module '{dependency}'"
    elif isinstance(exc, AttributeError):
        detail = f"missing attribute '{attribute_name}'"
    elif isinstance(exc, TypeError):
        detail = f"invalid entrypoint '{attribute_name}'"
    else:
        detail = f"{type(exc).__name__} while importing '{module_name}'"

    return StartupPreflightError(
        f"Startup preflight failed for {entrypoint} entrypoint "
        f"'{module_name}:{attribute_name}': {detail}"
    )


def preflight_startup() -> None:
    """Carga todos los entrypoints antes de crear cualquier child process."""
    for entrypoint, module_name, attribute_name in STARTUP_ENTRYPOINTS:
        try:
            module = importlib.import_module(module_name)
            entrypoint_object = getattr(module, attribute_name)
            if not callable(entrypoint_object):
                raise TypeError(
                    f"required entrypoint '{attribute_name}' is not callable"
                )
        except StartupPreflightError:
            raise
        except Exception as exc:
            raise _preflight_error(
                entrypoint,
                module_name,
                attribute_name,
                exc,
            ) from exc


def run_fastapi():
    """Inicia el servidor de API en el puerto 8000."""
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=False)


def run_telegram_bot():
    """Inicia el polling del bot de Telegram."""
    from src.bot.main import create_bot_app

    app = create_bot_app()
    app.run_polling()


def run_discord_bot():
    """Inicia el cliente del bot de Discord."""
    from src.discord.bot import run_discord_bot

    run_discord_bot()


def main() -> int:
    print("🚀 Iniciando ecosistema multi-plataforma (FastAPI + Telegram + Discord)...")

    try:
        preflight_startup()
    except StartupPreflightError as exc:
        print(f"[STARTUP PREFLIGHT] FAIL: {exc}", file=sys.stderr)
        return 1

    # Crear procesos independientes
    p_api = multiprocessing.Process(target=run_fastapi, name="FastAPI-Server")
    p_tg = multiprocessing.Process(target=run_telegram_bot, name="Telegram-Bot")
    p_dc = multiprocessing.Process(target=run_discord_bot, name="Discord-Bot")

    processes = [p_api, p_tg, p_dc]

    for p in processes:
        p.start()

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo todos los servicios de forma limpia...")
        for p in processes:
            p.terminate()
            p.join()
        print("✓ Todos los procesos han sido finalizados.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
