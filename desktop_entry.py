from __future__ import annotations

import os
from pathlib import Path
import queue
import subprocess
import sys
import traceback

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
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
    from bot_ia.interfaces.telegram_projects import TelegramProjectsAdapter
    from bot_ia.runtime import build_runtime

    load_dotenv(ROOT / ".env")
    try:
        runtime = build_runtime(ROOT)
        universe_id = os.getenv("BOT_IA_UNIVERSE", "one_neko_punch")
        provider_id = os.getenv("BOT_IA_PROVIDER", "openai")
        application = runtime.build_application(default_universe_id=universe_id, provider_id=provider_id)
        client = TelegramApiClient.from_environment()
        if not client.smoke_test():
            raise RuntimeError("Telegram getMe check failed")
        _telegram_log("Telegram: conexión OK; polling iniciado.")
        result = TelegramPoller(client, TelegramProjectsAdapter(application, runtime), logger=_telegram_log).run()
        _telegram_log(f"Telegram: detenido polls={result.polls} received={result.updates_received} processed={result.updates_processed} sent={result.responses_sent} errors={result.transport_errors}")
        runtime.memory_store.close()
        return 0
    except Exception as error:
        _telegram_log(f"Telegram ERROR: {type(error).__name__}: {error}")
        _telegram_log(traceback.format_exc())
        return 1


def _install_threadsafe_desktop():
    import desktop

    original_init = desktop.BotIADesktop.__init__
    original_close = desktop.BotIADesktop.close

    def init(self):
        self._ui_queue = queue.Queue()
        original_init(self)
        self._drain_ui_queue()

    def drain(self):
        while True:
            try:
                kind, payload = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "response":
                self.last_execution = payload[0]
                self._append("IA-chan", payload[1])
            elif kind == "error":
                self._append("BOT-IA", payload)
            elif kind == "busy":
                self._set_busy(payload)
            elif kind == "refresh":
                self.refresh_dashboard()
            elif kind == "telegram_status":
                self.telegram_button.configure(text=payload)
        if self.root.winfo_exists():
            self.root.after(50, self._drain_ui_queue)

    def handle_message(self, message: str, allow_api: bool) -> None:
        try:
            response = self.application.handle(
                desktop.ApplicationRequest("desktop-user", "desktop-session", message, allow_external_api=allow_api)
            )
            text = response.text
            if response.decision.external_api_authorized:
                text = "🔎 PROPUESTA EXTERNA (sin convertir en canon):\n\n" + text
            self._ui_queue.put(("response", (response.execution, text)))
        except Exception as error:
            self._ui_queue.put(("error", f"No pude procesar la consulta de forma segura: {type(error).__name__}: {error}"))
        finally:
            self._ui_queue.put(("busy", False))
            self._ui_queue.put(("refresh", None))

    def start_telegram(self):
        process = getattr(self, "telegram_process", None)
        if process is not None and process.poll() is None:
            self._append("BOT-IA", "Telegram ya está iniciado.")
            return
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            self._append("BOT-IA", "Telegram no está configurado. Añade TELEGRAM_BOT_TOKEN en la configuración y vuelve a iniciar Telegram.")
            return
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(SRC)
            if getattr(sys, "frozen", False):
                command = [sys.executable, "--telegram-worker"]
            else:
                command = [sys.executable, "-m", "desktop_entry", "--telegram-worker"]
            self.telegram_process = subprocess.Popen(command, cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.telegram_button.configure(text="● Telegram iniciando…")
            self._append("BOT-IA", "Telegram está comprobando el token y conectándose. Registro: work\\telegram.log")
            self._watch_telegram()
        except Exception as error:
            self._append("BOT-IA", f"No se pudo iniciar Telegram: {type(error).__name__}: {error}")

    def watch_telegram(self):
        process = getattr(self, "telegram_process", None)
        if process is None:
            return
        code = process.poll()
        if code is None:
            self.telegram_button.configure(text="● Telegram activo")
            self.root.after(1000, self._watch_telegram)
            return
        self.telegram_button.configure(text="▶ Iniciar en Telegram")
        log = _log_path()
        detail = "" if not log.is_file() else log.read_text(encoding="utf-8", errors="replace")[-2500:]
        if code != 0:
            self._append("BOT-IA", "Telegram se detuvo con error. Revisa work\\telegram.log.\n\n" + detail)
        else:
            self._append("BOT-IA", "Telegram se detuvo correctamente.")

    def close(self):
        process = getattr(self, "telegram_process", None)
        if process is not None and process.poll() is None:
            process.terminate()
        original_close(self)

    desktop.BotIADesktop.__init__ = init
    desktop.BotIADesktop._drain_ui_queue = drain
    desktop.BotIADesktop._handle_message = handle_message
    desktop.BotIADesktop.start_telegram = start_telegram
    desktop.BotIADesktop._watch_telegram = watch_telegram
    desktop.BotIADesktop.close = close
    return desktop


def main() -> None:
    if "--telegram-worker" in sys.argv:
        raise SystemExit(_run_telegram_worker())
    desktop = _install_threadsafe_desktop()
    app = desktop.BotIADesktop()
    app.root.mainloop()


if __name__ == "__main__":
    main()
