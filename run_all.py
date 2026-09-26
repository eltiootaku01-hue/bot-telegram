# -*- coding: utf-8 -*-
import multiprocessing
import os
import sys
import uvicorn

# Permitir importaciones relativas desde la raíz
sys.path.append(os.path.abspath(os.path.dirname(__file__)))


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


if __name__ == "__main__":
    print("🚀 Iniciando ecosistema multi-plataforma (FastAPI + Telegram + Discord)...")

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
