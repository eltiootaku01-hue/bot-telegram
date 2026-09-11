from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from dotenv import set_key
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover - packaged build installs python-dotenv
    set_key = None
    dotenv_values = None

from app.services.launcher_supervisor import LauncherSupervisor
from app.services.process_manager import ProcessManager


SOURCE_ROOT = Path(__file__).resolve().parent.parent
FROZEN_ROOT = Path(sys.executable).resolve().parent
ROOT = FROZEN_ROOT if getattr(sys, "frozen", False) else SOURCE_ROOT
ENV_PATH = ROOT / ".env"

BOTS = {
    "cari": ("Cari", "Moderación y comunidad", "app.bots.cari", "bots/Cari.exe"),
    "sunna": ("Sunna", "WaifuMon", "app.bots.sunna", "bots/Sunna.exe"),
    "cami": ("Cami", "Analítica y control", "app.bots.cami", "bots/Cami.exe"),
    "chie": ("Chie", "Coordinación y salud", "app.bots.chie", "bots/Chie.exe"),
}

ENV_DEFAULTS = {
    "BOT_IDENTITY": "cari",
    "LOG_LEVEL": "INFO",
    "DATABASE_URL": "sqlite+aiosqlite:///./data/bot.db",
    "ADMIN_USER_ID": "0",
    "MEDIA_STORAGE_CHAT_ID": "0",
    "PUBLISH_PAGE_CHAT_ID": "0",
    "AI_ENABLED": "false",
}

AI_FIELDS = (
    ("GEMINI_API_KEY", "Gemini API key"),
    ("GROQ_API_KEY", "Groq API key"),
    ("CEREBRAS_API_KEY", "Cerebras API key"),
    ("OPENROUTER_API_KEY", "OpenRouter API key"),
)


class BotLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bot Manager")
        self.geometry("900x760")
        self.minsize(900, 700)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.manager = ProcessManager(self._command, cwd=str(ROOT), grace_seconds=1.5)
        self.supervisor = LauncherSupervisor(self.manager)
        self.ai_global_var = tk.BooleanVar(value=False)
        self.ai_bot_vars: dict[str, tk.BooleanVar] = {}
        self.bot_vars: dict[str, dict[str, tk.StringVar]] = {}
        self.ai_vars: dict[str, tk.StringVar] = {}
        self.status = tk.StringVar(value="Configurá los bots y tocá Comenzar")
        self._dashboard_cards: dict[str, ttk.LabelFrame] = {}
        self._startup_poll_id: str | None = None
        self._closing = False
        self._build_setup()

    @property
    def processes(self) -> dict[str, subprocess.Popen[str]]:
        return self.manager.active_processes()

    def _build_setup(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

        outer = ttk.Frame(self, padding=24)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="BOT MANAGER", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Configuración local. La IA y las APIs son opcionales; los bots no dependen de ellas para iniciar.",
        ).pack(anchor="w", pady=(2, 18))

        bots_box = ttk.LabelFrame(outer, text="Bots de Telegram", padding=14)
        bots_box.pack(fill="x")
        headers = ("Bot", "Enlace", "Token")
        for column, header in enumerate(headers):
            ttk.Label(bots_box, text=header, font=("Segoe UI", 9, "bold")).grid(
                row=0, column=column, sticky="w", padx=5, pady=(0, 8)
            )
        bots_box.columnconfigure(1, weight=1)
        bots_box.columnconfigure(2, weight=2)

        values = self._load_env()
        for row, (key, (label, role, _, _)) in enumerate(BOTS.items(), start=1):
            ttk.Label(bots_box, text=f"{label}\n{role}").grid(row=row, column=0, sticky="w", padx=5, pady=6)
            link = tk.StringVar(value=values.get(f"BOT_LINK_{key.upper()}", "") or "")
            token = tk.StringVar(value=values.get(f"BOT_TOKEN_{key.upper()}", "") or "")
            self.bot_vars[key] = {"link": link, "token": token}
            ttk.Entry(bots_box, textvariable=link).grid(row=row, column=1, sticky="ew", padx=5, pady=6)
            ttk.Entry(bots_box, textvariable=token, show="•").grid(row=row, column=2, sticky="ew", padx=5, pady=6)

        ai_box = ttk.LabelFrame(outer, text="IA opcional", padding=14)
        ai_box.pack(fill="x", pady=(16, 0))
        ai_box.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            ai_box,
            text="IA general disponible",
            variable=self.ai_global_var,
            command=self._sync_ai_controls,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 8))
        for row, (env_name, label) in enumerate(AI_FIELDS, start=1):
            ttk.Label(ai_box, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=4)
            value = tk.StringVar(value=values.get(env_name, "") or "")
            self.ai_vars[env_name] = value
            ttk.Entry(ai_box, textvariable=value, show="•").grid(row=row, column=1, sticky="ew", padx=5, pady=4)

        per_bot = ttk.Frame(ai_box)
        per_bot.grid(row=5, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 0))
        for index, key in enumerate(BOTS):
            self.ai_bot_vars[key] = tk.BooleanVar(value=False)
            ttk.Checkbutton(per_bot, text=f"IA {BOTS[key][0]}", variable=self.ai_bot_vars[key]).grid(
                row=0, column=index, padx=(0, 14)
            )
        self.ai_global_var.set(values.get("AI_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"})
        self._sync_ai_controls()

        options = ttk.Frame(outer)
        options.pack(fill="x", pady=(16, 0))
        ttk.Label(options, text="Proveedor preferido (opcional)").grid(row=0, column=0, sticky="w")
        self.provider_var = tk.StringVar(value=values.get("LLM_PROVIDER", "") or "")
        ttk.Combobox(
            options,
            textvariable=self.provider_var,
            values=("", "ollama", "gemini", "groq", "cerebras", "openrouter"),
            state="readonly",
            width=18,
        ).grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(options, text="Modelo").grid(row=0, column=2, sticky="w", padx=(20, 0))
        self.model_var = tk.StringVar(value=values.get("LLM_MODEL", "") or values.get("OLLAMA_MODEL", "llama3.2:1b") or "")
        ttk.Entry(options, textvariable=self.model_var, width=28).grid(row=0, column=3, sticky="ew", padx=10)
        options.columnconfigure(3, weight=1)

        infra = ttk.Frame(outer)
        infra.pack(fill="x", pady=(12, 0))
        self.admin_var = tk.StringVar(value=values.get("ADMIN_USER_ID", "0") or "0")
        self.media_var = tk.StringVar(value=values.get("MEDIA_STORAGE_CHAT_ID", "0") or "0")
        ttk.Label(infra, text="Admin Telegram ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(infra, textvariable=self.admin_var, width=16).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(infra, text="Media vault chat ID").grid(row=0, column=2, sticky="w", padx=(20, 0))
        ttk.Entry(infra, textvariable=self.media_var, width=16).grid(row=0, column=3, sticky="w", padx=8)

        note = ttk.Label(
            outer,
            text="Los tokens y claves se guardan solamente en .env local (no se sube a Git).\n"
            "Si la IA está apagada, ningún bot debe invocar un LLM.",
        )
        note.pack(anchor="w", pady=(16, 8))

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(4, 0))
        ttk.Button(actions, text="Guardar configuración", command=self.save_config).pack(side="left")
        ttk.Button(actions, text="Comenzar", command=self.start_all).pack(side="right")
        ttk.Label(outer, textvariable=self.status, anchor="w").pack(fill="x", pady=(12, 0))

    def _sync_ai_controls(self) -> None:
        enabled = self.ai_global_var.get()
        for variable in self.ai_bot_vars.values():
            if not enabled:
                variable.set(False)

    def _load_env(self) -> dict[str, str]:
        if dotenv_values is not None and ENV_PATH.exists():
            return {key: value or "" for key, value in dotenv_values(ENV_PATH).items() if key}
        if not ENV_PATH.exists():
            return dict(ENV_DEFAULTS)
        result: dict[str, str] = dict(ENV_DEFAULTS)
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip('"')
        return result

    def save_config(self) -> bool:
        if set_key is None:
            messagebox.showerror("Configuración", "Falta python-dotenv. Ejecutá el instalador/build del proyecto.")
            return False

        ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not ENV_PATH.exists():
            ENV_PATH.write_text("# Generated by Bot Manager\n", encoding="utf-8")

        values: dict[str, str] = {}
        for key, fields in self.bot_vars.items():
            values[f"BOT_LINK_{key.upper()}"] = fields["link"].get().strip()
            values[f"BOT_TOKEN_{key.upper()}"] = fields["token"].get().strip()
        values.update({
            "LLM_PROVIDER": self.provider_var.get().strip(),
            "LLM_MODEL": self.model_var.get().strip(),
            "OLLAMA_MODEL": self.model_var.get().strip() or "llama3.2:1b",
            "ADMIN_USER_ID": self.admin_var.get().strip() or "0",
            "MEDIA_STORAGE_CHAT_ID": self.media_var.get().strip() or "0",
            "BOT_IDENTITY": "cari",
            "AI_ENABLED": "true" if self.ai_global_var.get() else "false",
        })
        for key, variable in self.ai_bot_vars.items():
            values[f"AI_ENABLED_{key.upper()}"] = "true" if variable.get() else "false"
        for env_name, value in self.ai_vars.items():
            values[env_name] = value.get().strip()

        for key, value in {**ENV_DEFAULTS, **values}.items():
            set_key(str(ENV_PATH), key, value, quote_mode="auto")
        self.status.set("Configuración guardada en .env")
        return True

    def _missing_required(self) -> list[str]:
        missing: list[str] = []
        for key, fields in self.bot_vars.items():
            if not fields["link"].get().strip():
                missing.append(f"Enlace de {key.title()}")
            if not fields["token"].get().strip():
                missing.append(f"Token de {key.title()}")
        return missing

    def start_all(self) -> None:
        missing = self._missing_required()
        if missing:
            messagebox.showwarning(
                "Falta configuración",
                "Antes de comenzar completá:\n\n" + "\n".join(f"• {item}" for item in missing),
            )
            return
        if not self.save_config():
            return

        if self.supervisor.running:
            self.status.set("Ya hay un arranque en curso")
            return
        self.supervisor.stop_all()
        self.status.set("Iniciando bots en secuencia y comprobando salud...")
        self.update_idletasks()
        if not self.supervisor.start_all(tuple(BOTS)):
            self.status.set("No se pudo iniciar el supervisor")
            return
        self._schedule_startup_poll()

    def _schedule_startup_poll(self) -> None:
        if self._startup_poll_id is not None:
            self.after_cancel(self._startup_poll_id)
        self._startup_poll_id = self.after(50, self._poll_startup_result)

    def _poll_startup_result(self) -> None:
        self._startup_poll_id = None
        if self._closing:
            return
        result = self.supervisor.poll_result()
        if result is None:
            self._schedule_startup_poll()
            return
        if result.error is not None:
            self.status.set("Inicio detenido por un error inesperado")
            messagebox.showerror("Error de inicio", str(result.error))
            return
        startup = result.result
        if startup is None:
            self.status.set("El supervisor terminó sin resultado")
            return
        if startup.failure is not None:
            failure = startup.failure
            details = self.manager.last_output.get(failure.identity, ())
            lines = [f"Bot: {failure.identity.title()}", f"Código de salida: {failure.returncode}", "", "Salida original:"]
            lines.extend(f"[{event.stream}] {event.line}" for event in details)
            if len(lines) == 5:
                lines.append("(El proceso terminó sin producir salida capturada.)")
            self.status.set(f"Inicio detenido por fallo en {failure.identity.title()}")
            messagebox.showerror("Error de inicio", "\n".join(lines))
            return
        self._build_dashboard()

    def _command(self, key: str) -> list[str]:
        _, _, module, executable = BOTS[key]
        if getattr(sys, "frozen", False):
            path = ROOT / executable
            if not path.exists():
                raise FileNotFoundError(
                    f"No existe {path}. Ejecutá tools\\build_launcher.bat para generar los bots."
                )
            return [str(path)]
        return [sys.executable, "-m", module]

    def _launch(self, key: str) -> None:
        self.manager.launch(key)

    def _build_dashboard(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

        outer = ttk.Frame(self, padding=24)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="BOT MANAGER", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Panel de control · supervisión de procesos activa").pack(anchor="w", pady=(2, 18))

        ai_panel = ttk.LabelFrame(outer, text="IA", padding=12)
        ai_panel.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(ai_panel, text="IA GENERAL", variable=self.ai_global_var, command=self._toggle_global_ai).pack(side="left")
        self.ai_state_label = ttk.Label(ai_panel, text="🔒 OFF")
        self.ai_state_label.pack(side="left", padx=14)
        ttk.Label(ai_panel, text="La IA no participa en el arranque ni en diagnósticos deterministas.").pack(side="right")

        grid = ttk.Frame(outer)
        grid.pack(fill="both", expand=True)
        self._dashboard_cards = {}
        for index, key in enumerate(BOTS):
            label, role, _, _ = BOTS[key]
            card = ttk.LabelFrame(grid, text=label, padding=14)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=6, pady=6)
            ttk.Label(card, text=role).pack(anchor="w")
            state = tk.StringVar()
            setattr(card, "_state", state)
            ai_state = tk.StringVar()
            setattr(card, "_ai_state", ai_state)
            ttk.Label(card, textvariable=state).pack(anchor="w", pady=(8, 2))
            ttk.Label(card, textvariable=ai_state).pack(anchor="w", pady=(0, 10))
            ttk.Button(card, text="Iniciar / detener", command=lambda name=key: self.toggle(name)).pack(fill="x")
            self._dashboard_cards[key] = card
            grid.columnconfigure(index % 2, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(18, 0))
        ttk.Button(actions, text="Configuración", command=self._build_setup).pack(side="left")
        ttk.Button(actions, text="Detener todos", command=self.stop_all).pack(side="right")
        ttk.Label(outer, textvariable=self.status, anchor="w").pack(fill="x", pady=(12, 0))
        self._refresh_ai_label()
        self.after(300, self.refresh_status)

    def _toggle_global_ai(self) -> None:
        if not self.ai_global_var.get():
            for variable in self.ai_bot_vars.values():
                variable.set(False)
        self._refresh_ai_label()

    def _refresh_ai_label(self) -> None:
        if hasattr(self, "ai_state_label"):
            self.ai_state_label.configure(text="🟢 ON" if self.ai_global_var.get() else "🔒 OFF")
        for key, card in self._dashboard_cards.items():
            state = getattr(card, "_ai_state", None)
            if state is not None:
                enabled = self.ai_global_var.get() and self.ai_bot_vars.get(key, tk.BooleanVar()).get()
                state.set("🟢 IA disponible" if enabled else "🔒 IA desactivada")

    def toggle(self, key: str) -> None:
        process = self.processes.get(key)
        if process is not None and process.poll() is None:
            self.manager.stop(key, process)
            self.status.set(f"{key.title()} detenido")
        else:
            try:
                self.manager.launch(key)
                self.status.set(f"{key.title()} iniciado; comprobando salud...")
                self.after(0, lambda name=key: self._check_single_start(name))
            except (OSError, FileNotFoundError) as exc:
                self.status.set(f"Error al iniciar {key.title()}")
                messagebox.showerror("Inicio", str(exc))
        self.refresh_status()

    def _check_single_start(self, key: str) -> None:
        process = self.processes.get(key)
        if process is None:
            return
        if not self.manager.check_health(key, process):
            details = self.manager.last_output.get(key, ())
            lines = [f"Bot: {key.title()}", f"Código de salida: {process.poll()}", "", "Salida original:"]
            lines.extend(f"[{event.stream}] {event.line}" for event in details)
            self.manager.stop(key, process)
            self.status.set(f"Inicio detenido por fallo en {key.title()}")
            messagebox.showerror("Error de inicio", "\n".join(lines))
        else:
            self.status.set(f"{key.title()} activo")
        self.refresh_status()

    def refresh_status(self) -> None:
        self.manager.drain_output()
        self.manager.reap_finished()
        for key, card in self._dashboard_cards.items():
            process = self.processes.get(key)
            state = getattr(card, "_state", None)
            if state is not None:
                state.set("● Ejecutándose" if process and process.poll() is None else "○ Detenido")
        self._refresh_ai_label()
        if self.winfo_exists():
            self.after(1000, self.refresh_status)

    def stop_all(self, *, silent: bool = False) -> None:
        self.supervisor.stop_all()
        if not silent:
            self.status.set("Todos los bots están detenidos")

    def close(self) -> None:
        self._closing = True
        if self._startup_poll_id is not None:
            self.after_cancel(self._startup_poll_id)
            self._startup_poll_id = None
        self.stop_all(silent=True)
        self.destroy()


if __name__ == "__main__":
    BotLauncher().mainloop()
