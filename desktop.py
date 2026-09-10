from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from bot_ia.config.dotenv import load_dotenv
from bot_ia.core.application import ApplicationRequest
from bot_ia.core.context_sharing import build_shared_context
from bot_ia.core.creative_assist import expand_scene_sketch
from bot_ia.runtime import build_runtime


MENU_ACTIONS = {
    "📖 Novela": "Quiero trabajar en One Neko Punch.",
    "📚 Biblioteca": "¿Qué información y documentos tengo disponibles en la biblioteca local?",
    "🧭 Continuidad": "Quiero revisar la continuidad de lo que estamos escribiendo y saber dónde quedamos.",
    "💡 Ideas": "Quiero ideas para continuar la novela usando la continuidad y personajes establecidos.",
    "🔎 Investigar": "Quiero investigar una duda usando primero la biblioteca local.",
    "🧰 Destrabar escena": None,
    "🔗 Compartir contexto": None,
    "📊 Estado API": None,
    "📈 Progreso": None,
    "❓ Ayuda": "¿Cómo funciona BOT-IA y qué puede hacer?",
}


class BotIADesktop:
    def __init__(self) -> None:
        load_dotenv(ROOT / ".env")
        self.runtime = build_runtime(ROOT)
        default_universe = os.getenv("BOT_IA_UNIVERSE", "one_neko_punch")
        provider = os.getenv("BOT_IA_PROVIDER", "openai")
        self.application = self.runtime.build_application(default_universe_id=default_universe, provider_id=provider)
        self.default_universe = default_universe
        self.provider = provider
        self.telegram_process: subprocess.Popen[str] | None = None
        self.last_execution = None

        self.root = tk.Tk()
        self.root.title("BOT-IA")
        self.root.geometry("1120x760")
        self.root.minsize(900, 620)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._build_ui()
        self.refresh_dashboard()
        self._append("BOT-IA", "¡Hola! Soy IA-chan. Elige una opción o escribe directamente.\n\nLa API externa permanece desactivada hasta que tú la autorices para una consulta.")

    def _build_ui(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=14)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="🤖 BOT-IA", font=("Segoe UI", 22, "bold")).grid(row=0, column=0, sticky="w")
        self.active_label = ttk.Label(header, text="NOVELA ACTIVA: One Neko Punch", font=("Segoe UI", 11, "bold"))
        self.active_label.grid(row=0, column=1, sticky="w", padx=20)
        self.telegram_button = ttk.Button(header, text="▶ Iniciar en Telegram", command=self.start_telegram)
        self.telegram_button.grid(row=0, column=2, sticky="e")

        sidebar = ttk.LabelFrame(self.root, text="Menú", padding=10)
        sidebar.grid(row=1, column=0, sticky="ns", padx=(14, 7), pady=(0, 14))
        for row, label in enumerate(MENU_ACTIONS):
            ttk.Button(sidebar, text=label, width=24, command=lambda x=label: self.menu_click(x)).grid(row=row, column=0, sticky="ew", pady=3)
        ttk.Separator(sidebar).grid(row=len(MENU_ACTIONS), column=0, sticky="ew", pady=8)
        ttk.Button(sidebar, text="🔄 Actualizar estado", command=self.refresh_dashboard).grid(row=len(MENU_ACTIONS)+1, column=0, sticky="ew", pady=3)
        ttk.Button(sidebar, text="✖ Cerrar", command=self.close).grid(row=len(MENU_ACTIONS)+2, column=0, sticky="ew", pady=3)

        center = ttk.Frame(self.root, padding=(0, 0, 14, 14))
        center.grid(row=1, column=1, sticky="nsew")
        center.columnconfigure(0, weight=1)
        center.rowconfigure(0, weight=1)

        self.chat = tk.Text(center, wrap="word", state="disabled", font=("Segoe UI", 11), padx=12, pady=12)
        self.chat.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(center, orient="vertical", command=self.chat.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.chat.configure(yscrollcommand=scrollbar.set)

        composer = ttk.Frame(center, padding=(0, 10, 0, 0))
        composer.grid(row=1, column=0, columnspan=2, sticky="ew")
        composer.columnconfigure(0, weight=1)
        self.input = tk.Text(composer, height=4, wrap="word", font=("Segoe UI", 11))
        self.input.grid(row=0, column=0, sticky="ew")
        self.input.bind("<Control-Return>", lambda _event: self.send())
        ttk.Button(composer, text="Enviar", command=self.send).grid(row=0, column=1, sticky="ns", padx=(8, 0))

        self.api_authorized = tk.BooleanVar(value=False)
        ttk.Checkbutton(composer, text="🔐 Autorizar API sólo para esta consulta", variable=self.api_authorized).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(composer, text="Ctrl+Enter = enviar | API desactivada por defecto", foreground="#666").grid(row=1, column=1, sticky="e", pady=(6, 0))

        dashboard = ttk.LabelFrame(center, text="Estado", padding=8)
        dashboard.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for col in range(3):
            dashboard.columnconfigure(col, weight=1)
        self.library_bar = ttk.Progressbar(dashboard, maximum=100)
        self.universe_bar = ttk.Progressbar(dashboard, maximum=100)
        self.provider_bar = ttk.Progressbar(dashboard, maximum=100)
        self.library_text = ttk.Label(dashboard)
        self.universe_text = ttk.Label(dashboard)
        self.provider_text = ttk.Label(dashboard)
        for col, (bar, text) in enumerate(((self.library_bar, self.library_text), (self.universe_bar, self.universe_text), (self.provider_bar, self.provider_text))):
            bar.grid(row=0, column=col, sticky="ew", padx=6)
            text.grid(row=1, column=col, sticky="w", padx=6, pady=(3, 0))

    def _append(self, speaker: str, text: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{speaker}:\n{text.strip()}\n\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def send(self) -> None:
        message = self.input.get("1.0", "end").strip()
        if not message:
            return
        self.input.delete("1.0", "end")
        self._append("Tú", message)
        self._set_busy(True)
        allow_api = self.api_authorized.get()
        self.api_authorized.set(False)
        threading.Thread(target=self._handle_message, args=(message, allow_api), daemon=True).start()

    def _handle_message(self, message: str, allow_api: bool) -> None:
        try:
            response = self.application.handle(ApplicationRequest("desktop-user", "desktop-session", message, allow_external_api=allow_api))
            self.last_execution = response.execution
            text = response.text
            if response.decision.external_api_authorized:
                text = "🔎 PROPUESTA EXTERNA (sin convertir en canon):\n\n" + text
            self.root.after(0, lambda: self._append("IA-chan", text))
        except Exception as error:
            self.root.after(0, lambda: self._append("BOT-IA", f"No pude procesar la consulta de forma segura: {error}"))
        finally:
            self.root.after(0, lambda: self._set_busy(False))
            self.root.after(0, self.refresh_dashboard)

    def menu_click(self, label: str) -> None:
        if label == "🧰 Destrabar escena":
            self._append("BOT-IA", "🧰 Escribe un boceto corto y lo convertiré en preguntas de desarrollo sin consumir API.")
            return
        if label == "🔗 Compartir contexto":
            self.share_context()
            return
        if label == "📊 Estado API":
            self.show_api_status()
            return
        if label == "📈 Progreso":
            self.show_progress()
            return
        action = MENU_ACTIONS[label]
        if action:
            self.input.delete("1.0", "end")
            self.input.insert("1.0", action)
            self.send()

    def share_context(self) -> None:
        """Prepara y copia sólo evidencia recuperada; nunca hace una llamada de red."""
        if self.last_execution is None:
            self._append("BOT-IA", "🔗 Todavía no hay una consulta procesada con evidencia para compartir. Primero realiza una consulta.")
            return
        try:
            shared = build_shared_context(self.last_execution)
        except Exception as error:
            self._append("BOT-IA", f"No pude preparar el contexto de forma segura: {error}")
            return

        preview = tk.Toplevel(self.root)
        preview.title("BOT-IA — Compartir contexto")
        preview.geometry("820x620")
        preview.transient(self.root)
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(1, weight=1)
        ttk.Label(
            preview,
            text="🔗 CONTEXTO PARA IA EXTERNA",
            font=("Segoe UI", 15, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=10)
        text = tk.Text(preview, wrap="word", font=("Consolas", 10))
        text.grid(row=1, column=0, sticky="nsew", padx=12)
        text.insert("1.0", shared.text)
        text.configure(state="disabled")
        buttons = ttk.Frame(preview, padding=12)
        buttons.grid(row=2, column=0, sticky="ew")
        ttk.Label(
            buttons,
            text="Esto sólo copia el contexto. BOT-IA no envía nada a Internet desde este botón.",
        ).pack(side="left")

        def copy_context() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(shared.text)
            self.root.update()
            self._append("BOT-IA", "🔗 Contexto copiado al portapapeles. Revísalo antes de pegarlo en una IA externa.")
            preview.destroy()

        ttk.Button(buttons, text="📋 Copiar contexto", command=copy_context).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Cancelar", command=preview.destroy).pack(side="right")

    def show_api_status(self) -> None:
        health = getattr(self.runtime.provider_manager, "_health", {})
        if not health:
            self._append("BOT-IA", "📊 No hay datos de uso de providers todavía.")
            return
        lines = ["📊 ESTADO API"]
        for (provider, account), record in sorted(health.items()):
            lines.append(f"• {provider}/{account}: estado={getattr(record.state, 'value', record.state)}, solicitudes={record.total_requests}, tokens conocidos={record.total_tokens}")
        lines.append("\nLos porcentajes de cuota real del proveedor no se inventan: sólo se muestran métricas conocidas por BOT-IA.")
        self._append("BOT-IA", "\n".join(lines))

    def show_progress(self) -> None:
        target = int(os.getenv("BOT_IA_TARGET_CHAPTERS", "0") or "0")
        universe = next((u for u in self.runtime.universes if u.definition.universe_id == self.default_universe), None)
        count = 0
        if universe:
            import re
            count = len({int(n) for e in universe.entries for n in re.findall(r"(?:cap(?:ítulo)?|cap)[ _-]?(\d+)", e.record.path.casefold())})
        if target > 0:
            pct = min(100, 100 * count / target)
            self._append("BOT-IA", f"📈 Progreso documental: {pct:.1f}% ({count}/{target} capítulos detectados).\nEsto mide documentación frente al objetivo, no calidad ni porcentaje de historia terminada.")
        else:
            self._append("BOT-IA", f"📈 Capítulos detectados: {count}.\nNo calculo un porcentaje porque BOT_IA_TARGET_CHAPTERS no está configurado.")

    def refresh_dashboard(self) -> None:
        try:
            total_config = len(self.runtime.config.universes)
            active = len(self.runtime.universes)
            universe_pct = 100 * active / total_config if total_config else 0
            entries = sum(len(u.entries) for u in self.runtime.universes)
            library_pct = 100 if entries > 0 else 0
            configured = sum(1 for p in self.runtime.config.providers if p.enabled)
            provider_pct = 100 * configured / len(self.runtime.config.providers) if self.runtime.config.providers else 0
            self.library_bar["value"] = library_pct
            self.universe_bar["value"] = universe_pct
            self.provider_bar["value"] = provider_pct
            self.library_text["text"] = f"Biblioteca: {library_pct:.0f}% ({entries} fuentes indexadas)"
            self.universe_text["text"] = f"Universos: {universe_pct:.0f}% ({active}/{total_config} conectados)"
            self.provider_text["text"] = f"Providers: {provider_pct:.0f}% ({configured}/{len(self.runtime.config.providers)} habilitados)"
            self.active_label["text"] = f"NOVELA ACTIVA: {self.default_universe.replace('_', ' ').title()}"
        except Exception as error:
            self.library_text["text"] = f"Estado: error de runtime ({error})"

    def start_telegram(self) -> None:
        if self.telegram_process and self.telegram_process.poll() is None:
            messagebox.showinfo("BOT-IA", "Telegram ya está iniciado.")
            return
        try:
            if getattr(sys, "frozen", False):
                command = [sys.executable, "--mode", "telegram"]
            else:
                command = [sys.executable, "-m", "bot_ia", "--mode", "telegram"]
            env = os.environ.copy()
            env["PYTHONPATH"] = str(SRC)
            self.telegram_process = subprocess.Popen(command, cwd=str(ROOT), env=env)
            self.telegram_button.configure(text="● Telegram activo")
            self._append("BOT-IA", "Telegram iniciado en un proceso separado. Esta ventana sigue disponible.")
        except Exception as error:
            messagebox.showerror("Telegram", f"No se pudo iniciar Telegram:\n{error}")

    def _set_busy(self, busy: bool) -> None:
        self.root.title("BOT-IA — procesando..." if busy else "BOT-IA")

    def close(self) -> None:
        if self.telegram_process and self.telegram_process.poll() is None:
            self.telegram_process.terminate()
        try:
            self.runtime.memory_store.close()
        finally:
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    if "--mode" in sys.argv:
        from bot_ia.__main__ import main
        main()
    else:
        BotIADesktop().run()
