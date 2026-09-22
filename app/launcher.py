from __future__ import annotations

import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from tkinter import messagebox, ttk

try:
    from dotenv import set_key
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover - packaged build installs python-dotenv
    set_key = None
    dotenv_values = None

from app.gui.telegram_setup import TelegramSetupAssistant
from app.services.setup_checklist import build_setup_checklist
from app.services.telegram_setup import build_start_link
from app.services.launcher_supervisor import LauncherSupervisor
from app.services.process_manager import ProcessManager
from app.services.runtime_monitor import RuntimeMonitor, RuntimeSnapshot
from app.services.setup_validation import validate_setup


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
    "AUTHORIZED_CHAT_IDS": "",
    "ALLOW_ADMIN_PRIVATE_CHAT": "true",
    "ALLOW_USER_PRIVATE_CHAT": "true",
    "TMA_API_ENABLED": "true",
    "TMA_API_HOST": "0.0.0.0",
    "TMA_API_PORT": "8765",
    "TMA_BOT_IDENTITY": "sunna",
    "TMA_INIT_DATA_MAX_AGE_SECONDS": "3600",
    "TMA_ALLOWED_ORIGINS": "",
    "TMA_FRONTEND_BASE_URL": "https://eltiootaku01-hue.github.io/bot-telegram",
    "TMA_PREMIUM_TICKET_PRICE_STARS": "10",
    "TMA_STARTER_PACK_PRICE_STARS": "25",
    "AI_ENABLED": "false",
    "MASTER_TELEGRAM_ID": "0",
    "MASTER_USERNAME": "",
    "BASE_GROUP_CHAT_ID": "0",
    "HUMAN_VERIFICATION_TIMEOUT_SECONDS": "120",
    "HUMAN_VERIFICATION_RAID_WINDOW_SECONDS": "60",
    "HUMAN_VERIFICATION_RAID_THRESHOLD": "5",
    "HUMAN_VERIFICATION_RAID_TIMEOUT_SECONDS": "45",
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
        self.geometry("900x820")
        self.minsize(900, 760)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.manager = ProcessManager(self._command, cwd=str(ROOT), grace_seconds=1.5)
        self.supervisor = LauncherSupervisor(self.manager)
        self.runtime_monitor = RuntimeMonitor()
        self._runtime_queue: Queue[RuntimeSnapshot] = Queue(maxsize=1)
        self._runtime_lock = Lock()
        self._runtime_running = False
        self.ai_global_var = tk.BooleanVar(value=False)
        self.ai_bot_vars: dict[str, tk.BooleanVar] = {}
        self.bot_vars: dict[str, dict[str, tk.StringVar]] = {}
        self.ai_vars: dict[str, tk.StringVar] = {}
        self.master_var = tk.StringVar(value="0")
        self.master_username_var = tk.StringVar(value="")
        self.base_group_var = tk.StringVar(value="0")
        self.status = tk.StringVar(value="Configurá los bots y tocá Comenzar")
        self._dashboard_cards: dict[str, ttk.LabelFrame] = {}
        self._startup_poll_id: str | None = None
        self._runtime_poll_id: str | None = None
        self._closing = False
        self._reported_unexpected_exits: set[str] = set()
        self.tma_api: TmaApiServer | None = None
        self.tma_enabled_var = tk.BooleanVar(value=True)
        self.tma_host_var = tk.StringVar(value="0.0.0.0")
        self.tma_port_var = tk.StringVar(value="8765")
        self.tma_origins_var = tk.StringVar(value="")
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

        access_box = ttk.LabelFrame(outer, text="Seguridad de acceso de Telegram", padding=14)
        access_box.pack(fill="x", pady=(16, 0))
        access_box.columnconfigure(1, weight=1)
        ttk.Label(
            access_box,
            text="Chats de grupos autorizados (IDs separados por coma)",
        ).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.authorized_chats_var = tk.StringVar(value=values.get("AUTHORIZED_CHAT_IDS", "") or "")
        ttk.Entry(access_box, textvariable=self.authorized_chats_var).grid(
            row=0, column=1, sticky="ew", padx=5, pady=5
        )
        self.allow_user_private_var = tk.BooleanVar(
            value=(values.get("ALLOW_USER_PRIVATE_CHAT", "true") or "true").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        ttk.Checkbutton(
            access_box,
            text="Permitir funciones privadas a usuarios normales",
            variable=self.allow_user_private_var,
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 2))
        self.allow_admin_private_var = tk.BooleanVar(
            value=(values.get("ALLOW_ADMIN_PRIVATE_CHAT", "true") or "true").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        ttk.Checkbutton(
            access_box,
            text="Permitir chat privado únicamente al ADMIN_USER_ID",
            variable=self.allow_admin_private_var,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 2))
        ttk.Label(
            access_box,
            text="Vacío = ningún grupo autorizado. Los IDs se validan nuevamente en el runtime.",
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 3))

        verification = ttk.LabelFrame(outer, text="Chie · verificación humana / anti-raid", padding=14)
        verification.pack(fill="x", pady=(12, 0))
        verification.columnconfigure(1, weight=1)
        self.verification_timeout_var = tk.StringVar(
            value=values.get("HUMAN_VERIFICATION_TIMEOUT_SECONDS", "120") or "120"
        )
        self.verification_raid_window_var = tk.StringVar(
            value=values.get("HUMAN_VERIFICATION_RAID_WINDOW_SECONDS", "60") or "60"
        )
        self.verification_raid_threshold_var = tk.StringVar(
            value=values.get("HUMAN_VERIFICATION_RAID_THRESHOLD", "5") or "5"
        )
        self.verification_raid_timeout_var = tk.StringVar(
            value=values.get("HUMAN_VERIFICATION_RAID_TIMEOUT_SECONDS", "45") or "45"
        )
        ttk.Label(verification, text="TTL normal (segundos)").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(verification, textvariable=self.verification_timeout_var, width=12).grid(
            row=0, column=1, sticky="w", padx=5, pady=4
        )
        ttk.Label(verification, text="Ventana anti-raid (segundos)").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(verification, textvariable=self.verification_raid_window_var, width=12).grid(
            row=1, column=1, sticky="w", padx=5, pady=4
        )
        ttk.Label(verification, text="Umbral de entradas").grid(row=2, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(verification, textvariable=self.verification_raid_threshold_var, width=12).grid(
            row=2, column=1, sticky="w", padx=5, pady=4
        )
        ttk.Label(verification, text="TTL durante oleada (segundos)").grid(row=3, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(verification, textvariable=self.verification_raid_timeout_var, width=12).grid(
            row=3, column=1, sticky="w", padx=5, pady=4
        )
        ttk.Label(
            verification,
            text="Chie restringe al entrar. Al vencer o responder 'Sí, soy un bot', expulsa y desbanea.",
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=5, pady=(6, 2))

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
            self.ai_bot_vars[key] = tk.BooleanVar(value=(values.get(f"AI_ENABLED_{key.upper()}", "") or "").strip().lower() in {"1", "true", "yes", "on"})
            ttk.Checkbutton(per_bot, text=f"IA {BOTS[key][0]}", variable=self.ai_bot_vars[key]).grid(
                row=0, column=index, padx=(0, 14)
            )
        self.ai_global_var.set(values.get("AI_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"})
        self._sync_ai_controls()

        tma_box = ttk.LabelFrame(outer, text="Telegram Mini App · API", padding=14)
        tma_box.pack(fill="x", pady=(16, 0))
        tma_box.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            tma_box,
            text="Activar API TMA al iniciar Bot Manager",
            variable=self.tma_enabled_var,
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 8))
        ttk.Label(tma_box, text="Host").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(tma_box, textvariable=self.tma_host_var, width=18).grid(row=1, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(tma_box, text="Puerto").grid(row=1, column=2, sticky="w", padx=(18, 5), pady=4)
        ttk.Entry(tma_box, textvariable=self.tma_port_var, width=10).grid(row=1, column=3, sticky="w", padx=5, pady=4)
        ttk.Label(tma_box, text="Orígenes CORS autorizados").grid(row=2, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(tma_box, textvariable=self.tma_origins_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=5, pady=4)
        ttk.Label(
            tma_box,
            text="Separá varios orígenes por coma. initData se valida en el servidor en cada GET/POST.",
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=5, pady=(4, 0))

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
        self.master_var.set(values.get("MASTER_TELEGRAM_ID", "") or self.admin_var.get() or "0")
        self.master_username_var.set(values.get("MASTER_USERNAME", "") or "")
        self.base_group_var.set(values.get("BASE_GROUP_CHAT_ID", "") or "0")
        self.tma_enabled_var.set(values.get("TMA_API_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"})
        self.tma_host_var.set(values.get("TMA_API_HOST", "0.0.0.0") or "0.0.0.0")
        self.tma_port_var.set(values.get("TMA_API_PORT", "8765") or "8765")
        self.tma_origins_var.set(values.get("TMA_ALLOWED_ORIGINS", "") or "")
        self.media_var = tk.StringVar(value=values.get("MEDIA_STORAGE_CHAT_ID", "0") or "0")
        self.publish_page_var = tk.StringVar(value=values.get("PUBLISH_PAGE_CHAT_ID", "0") or "0")
        ttk.Label(infra, text="Maestro / Jefe · ID Telegram").grid(row=0, column=0, sticky="w")
        ttk.Entry(infra, textvariable=self.master_var, width=16).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(infra, text="@usuario (referencia)").grid(row=0, column=2, sticky="w", padx=(18, 0))
        ttk.Entry(infra, textvariable=self.master_username_var, width=18).grid(row=0, column=3, sticky="w", padx=8)
        ttk.Label(infra, text="Grupo general / bienvenida").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(infra, textvariable=self.base_group_var, width=16).grid(row=1, column=1, sticky="w", padx=8, pady=(8, 0))
        ttk.Label(infra, text="Media vault chat ID").grid(row=0, column=4, sticky="w", padx=(18, 0))
        ttk.Entry(infra, textvariable=self.media_var, width=16).grid(row=0, column=5, sticky="w", padx=8)
        ttk.Label(infra, text="Página/Canal de publicaciones").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(infra, textvariable=self.publish_page_var, width=16).grid(row=1, column=3, sticky="w", padx=8, pady=(8, 0))
        ttk.Label(
            infra,
            text="El ID de Maestro/Jefe es la identidad de permisos. El @usuario es solo referencia visual; el teléfono no se usa como credencial.",
        ).grid(row=2, column=0, columnspan=6, sticky="w", pady=(6, 0))
        ttk.Button(
            infra,
            text="Obtener mi ID con Chie",
            command=self.open_master_id_helper,
        ).grid(row=0, column=6, sticky="w", padx=(12, 0))

        note = ttk.Label(
            outer,
            text="Los tokens y claves se guardan solamente en .env local (no se sube a Git).\n"
            "Si la IA está apagada, ningún bot debe invocar un LLM.",
        )
        note.pack(anchor="w", pady=(16, 8))

        checklist = ttk.LabelFrame(outer, text="Estado de preparación", padding=10)
        checklist.pack(fill="x", pady=(0, 10))
        self.setup_checklist_var = tk.StringVar()
        ttk.Label(checklist, textvariable=self.setup_checklist_var, justify="left").pack(anchor="w")
        ttk.Button(checklist, text="Actualizar estado", command=self.refresh_setup_checklist).pack(anchor="e", pady=(8, 0))
        self.refresh_setup_checklist()

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(4, 0))
        ttk.Button(actions, text="Asistente Telegram", command=self.open_telegram_assistant).pack(side="left")
        ttk.Button(actions, text="Guía BotFather / Telegram", command=self.show_telegram_manual).pack(side="left", padx=8)
        ttk.Button(actions, text="Guardar configuración", command=self.save_config).pack(side="left", padx=8)
        ttk.Button(actions, text="Comenzar", command=self.start_all).pack(side="right")
        ttk.Label(outer, textvariable=self.status, anchor="w").pack(fill="x", pady=(12, 0))

    def refresh_setup_checklist(self) -> None:
        checks = build_setup_checklist(
            bots={
                key: {
                    "link": fields["link"].get(),
                    "token": fields["token"].get(),
                }
                for key, fields in self.bot_vars.items()
            },
            master_id=self.master_var.get(),
            base_group_id=self.base_group_var.get(),
            authorized_chat_ids=self.authorized_chats_var.get(),
        )
        self.setup_checklist_var.set("\n".join(checks))

    def open_master_id_helper(self) -> None:
        link = self.bot_vars["chie"]["link"].get().strip()
        username = link.rsplit("/", 1)[-1].lstrip("@").split("?")[0] if link else ""
        if not username:
            messagebox.showwarning(
                "Maestro/Jefe",
                "Primero verificá el token de Chie en el Asistente Telegram para obtener su @username.",
                parent=self,
            )
            return
        webbrowser.open(build_start_link(username, "miid"))
        self.status.set("Telegram abrió Chie: pulsá Iniciar; Chie te mostrará tu ID.")

    def show_telegram_manual(self) -> None:
        manual = (
            "BOTFATHER\n"
            "1. Creá Cari, Sunna, Cami y Chie con @BotFather.\n"
            "2. Copiá cada token aquí y pulsá Verificar.\n"
            "3. Para que los bots reciban mensajes normales de grupos, revisá /setprivacy en @BotFather; "
            "los bots administradores reciben todos los mensajes.\n\n"
            "GRUPO BASE\n"
            "4. Agregá primero Chie al grupo general/bienvenida y dale permisos para eliminar, restringir y gestionar temas.\n"
            "5. Ejecutá /configurar con Chie.\n"
            "6. Copiá el ID negativo del grupo a Grupo base y autorizalo.\n"
            "7. Agregá Cari, Sunna y Cami con sus botones y revisá presencia.\n\n"
            "MAESTRO / JEFE\n"
            "8. Usá Obtener mi ID con Chie para conocer tu ID numérico.\n"
            "9. Pegá ese ID en Maestro/Jefe. Ese ID es el que usa el sistema para los permisos administrativos.\n\n"
            "IMPORTANTE\n"
            "El teléfono no se guarda ni se usa como credencial. El identificador operativo es el ID numérico de Telegram.\n"
            "Telegram sí permite enlaces start/startgroup para abrir un bot o preparar su incorporación a un grupo, "
            "pero la selección del grupo y la acción del usuario siguen formando parte del flujo oficial."
        )
        messagebox.showinfo("Guía rápida de Telegram", manual, parent=self)

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
            "MASTER_TELEGRAM_ID": (
                self.master_var.get().strip()
                if hasattr(self, "master_var")
                else self.admin_var.get().strip()
            ) or "0",
            "MASTER_USERNAME": (
                self.master_username_var.get().strip()
                if hasattr(self, "master_username_var")
                else ""
            ),
            "ADMIN_USER_ID": (
                (
                    self.master_var.get().strip()
                    if hasattr(self, "master_var")
                    else self.admin_var.get().strip()
                )
                or self.admin_var.get().strip()
                or "0"
            ),
            "BASE_GROUP_CHAT_ID": (
                self.base_group_var.get().strip()
                if hasattr(self, "base_group_var")
                else "0"
            ) or "0",
            "MEDIA_STORAGE_CHAT_ID": self.media_var.get().strip() or "0",
            "PUBLISH_PAGE_CHAT_ID": self.publish_page_var.get().strip() or "0",
            "AUTHORIZED_CHAT_IDS": self.authorized_chats_var.get().strip(),
            "ALLOW_ADMIN_PRIVATE_CHAT": "true" if self.allow_admin_private_var.get() else "false",
            "ALLOW_USER_PRIVATE_CHAT": "true" if self.allow_user_private_var.get() else "false",
            "HUMAN_VERIFICATION_TIMEOUT_SECONDS": self.verification_timeout_var.get().strip() or "120",
            "HUMAN_VERIFICATION_RAID_WINDOW_SECONDS": self.verification_raid_window_var.get().strip() or "60",
            "HUMAN_VERIFICATION_RAID_THRESHOLD": self.verification_raid_threshold_var.get().strip() or "5",
            "HUMAN_VERIFICATION_RAID_TIMEOUT_SECONDS": self.verification_raid_timeout_var.get().strip() or "45",
            "BOT_IDENTITY": "cari",
            "AI_ENABLED": "true" if self.ai_global_var.get() else "false",
            "TMA_API_ENABLED": "true" if self.tma_enabled_var.get() else "false",
            "TMA_API_HOST": self.tma_host_var.get().strip() or "0.0.0.0",
            "TMA_API_PORT": self.tma_port_var.get().strip() or "8765",
            "TMA_BOT_IDENTITY": "sunna",
            "TMA_INIT_DATA_MAX_AGE_SECONDS": "3600",
            "TMA_ALLOWED_ORIGINS": self.tma_origins_var.get().strip(),
            "TMA_FRONTEND_BASE_URL": "https://eltiootaku01-hue.github.io/bot-telegram",
            "TMA_PREMIUM_TICKET_PRICE_STARS": "10",
            "TMA_STARTER_PACK_PRICE_STARS": "25",
        })
        for key, variable in self.ai_bot_vars.items():
            values[f"AI_ENABLED_{key.upper()}"] = "true" if variable.get() else "false"
        for env_name, value in self.ai_vars.items():
            values[env_name] = value.get().strip()

        for key, value in {**ENV_DEFAULTS, **values}.items():
            set_key(str(ENV_PATH), key, value, quote_mode="auto")
        self.status.set("Configuración guardada en .env")
        return True

    def open_telegram_assistant(self) -> None:
        TelegramSetupAssistant(
            self,
            bots=BOTS,
            bot_vars=self.bot_vars,
            authorized_chats_var=self.authorized_chats_var,
            base_group_var=self.base_group_var,
        )

    def _missing_required(self) -> list[str]:
        missing: list[str] = []
        for key, fields in self.bot_vars.items():
            if not fields["token"].get().strip():
                missing.append(f"Token de {key.title()}")
        return missing

    def _validate_configuration(self) -> bool:
        result = validate_setup(
            bots={
                key: {
                    "link": fields["link"].get(),
                    "token": fields["token"].get(),
                }
                for key, fields in self.bot_vars.items()
            },
            authorized_chat_ids=self.authorized_chats_var.get(),
            admin_user_id=self.master_var.get(),
            allow_admin_private_chat=self.allow_admin_private_var.get(),
            allow_user_private_chat=self.allow_user_private_var.get(),
            media_storage_chat_id=self.media_var.get(),
            publish_page_chat_id=self.publish_page_var.get(),
            base_group_chat_id=self.base_group_var.get(),
            human_verification_timeout_seconds=self.verification_timeout_var.get(),
            human_verification_raid_window_seconds=self.verification_raid_window_var.get(),
            human_verification_raid_threshold=self.verification_raid_threshold_var.get(),
            human_verification_raid_timeout_seconds=self.verification_raid_timeout_var.get(),
        )
        if result.errors:
            messagebox.showerror(
                "Configuración inválida",
                "\n".join(f"• {error}" for error in result.errors),
            )
            return False
        if result.warnings:
            messagebox.showwarning(
                "Revisión de configuración",
                "\n".join(f"• {warning}" for warning in result.warnings),
            )
        return True

    def start_all(self) -> None:
        missing = self._missing_required()
        if missing:
            messagebox.showwarning(
                "Falta configuración",
                "Antes de comenzar completá:\n\n" + "\n".join(f"• {item}" for item in missing),
            )
            return
        if not self._validate_configuration():
            return
        if not self.save_config():
            return

        self._restart_tma_api()

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
        if startup.cancelled:
            self.status.set("Inicio cancelado; todos los bots están detenidos")
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
        ttk.Label(ai_panel, text="Opcional: el núcleo funciona sin IA ni APIs.").pack(side="right")

        monitor = ttk.LabelFrame(outer, text="SISTEMA / OLLAMA", padding=10)
        monitor.pack(fill="x", pady=(0, 10))
        self.system_state = tk.StringVar(value="CPU --   RAM --   DISCO --")
        self.ollama_state = tk.StringVar(value="OLLAMA: comprobando...")
        ttk.Label(monitor, textvariable=self.system_state, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Label(monitor, textvariable=self.ollama_state).pack(anchor="w", pady=(4, 0))

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
        self._schedule_runtime_poll()
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

    def _schedule_runtime_poll(self) -> None:
        if self._runtime_poll_id is not None:
            self.after_cancel(self._runtime_poll_id)
        self._runtime_poll_id = self.after(100, self._poll_runtime)
        self._start_runtime_snapshot()

    def _start_runtime_snapshot(self) -> None:
        with self._runtime_lock:
            if self._runtime_running or self._closing:
                return
            self._runtime_running = True
        Thread(target=self._read_runtime_snapshot, daemon=True, name="runtime-monitor").start()

    def _read_runtime_snapshot(self) -> None:
        try:
            result = self.runtime_monitor.snapshot(str(ROOT))
            try:
                self._runtime_queue.get_nowait()
            except Empty:
                pass
            self._runtime_queue.put_nowait(result)
        except Exception:
            pass
        finally:
            with self._runtime_lock:
                self._runtime_running = False

    def _poll_runtime(self) -> None:
        self._runtime_poll_id = None
        if self._closing:
            return
        try:
            result = self._runtime_queue.get_nowait()
        except Empty:
            result = None
        if result is not None:
            system = result.system
            self.system_state.set(
                f"CPU {system.cpu_percent:.0f}%   RAM {system.memory_percent:.0f}%   DISCO {system.disk_percent:.0f}%"
            )
            if result.ollama.online:
                model = result.ollama.running_models[0] if result.ollama.running_models else (
                    result.ollama.models[0] if result.ollama.models else "sin modelo"
                )
                self.ollama_state.set(f"OLLAMA: 🟢 ONLINE · Modelo: {model}")
            else:
                self.ollama_state.set("OLLAMA: ○ OFFLINE (opcional)")
        self._start_runtime_snapshot()
        self._runtime_poll_id = self.after(5000, self._poll_runtime)

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
        finished = self.manager.reap_finished()
        for key, returncode in finished:
            exit_info = self.manager.last_exit_for(key)
            if exit_info is None:
                continue
            if exit_info.expected:
                continue
            state = getattr(self._dashboard_cards.get(key), "_state", None)
            if state is not None:
                code = "sin código" if returncode is None else str(returncode)
                state.set(f"⚠ Terminó inesperadamente · código {code}")
            if key not in self._reported_unexpected_exits:
                self._reported_unexpected_exits.add(key)
                details = [
                    f"Bot: {key.title()}",
                    f"Código de salida: {'desconocido' if returncode is None else returncode}",
                    "",
                    "Salida capturada:",
                ]
                details.extend(f"[{event.stream}] {event.line}" for event in exit_info.output)
                if len(details) == 4:
                    details.append("(El proceso terminó sin producir salida capturada.)")
                self.status.set(f"{key.title()} terminó inesperadamente")
                messagebox.showerror("Bot detenido inesperadamente", "\n".join(details))
        for key, card in self._dashboard_cards.items():
            process = self.processes.get(key)
            state = getattr(card, "_state", None)
            if state is not None and process is not None and process.poll() is None:
                self._reported_unexpected_exits.discard(key)
                state.set("● Ejecutándose")
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
        if self._runtime_poll_id is not None:
            self.after_cancel(self._runtime_poll_id)
            self._runtime_poll_id = None
        self.stop_all(silent=True)
        self.destroy()


if __name__ == "__main__":
    BotLauncher().mainloop()
