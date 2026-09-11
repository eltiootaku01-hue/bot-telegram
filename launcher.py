from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
CORE_EXE = ROOT / "BOT-IA-Core.exe"
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen3:1.7b-q4_K_M"

PROVIDERS = {
    "OpenAI": ("openai", "OPENAI_API_KEY"),
    "Groq": ("groq", "GROQ_API_KEY"),
    "OpenRouter": ("openrouter", "OPENROUTER_API_KEY"),
    "Ollama local": ("ollama", None),
}


def _read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.is_file():
        return values
    for raw in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_env(*, universe: str, library: Path, provider: str, api_key: str, telegram_token: str) -> None:
    provider_id, key_name = PROVIDERS[provider]
    lines = [
        "# BOT-IA generated configuration. This file is local and must never be committed.",
        f"BOT_IA_UNIVERSE={universe}",
        f"BOT_IA_PROVIDER={provider_id}",
        f"BOT_IA_ENABLE_LOCAL_OLLAMA={'true' if provider_id == 'ollama' else 'false'}",
        f"BOT_IA_ONE_NEKO_PUNCH_ROOT={library}",
        "",
    ]

    for name in ("OPENAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        lines.append(f"{name}={api_key if name == key_name else ''}")

    lines.extend(
        [
            f"OLLAMA_BASE_URL={OLLAMA_BASE_URL}",
            f"TELEGRAM_BOT_TOKEN={telegram_token}",
        ]
    )
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _library_ok(path: Path) -> bool:
    return path.is_dir() and any(path.rglob("*.md"))


def _ollama_probe(*, base_url: str = OLLAMA_BASE_URL, timeout: float = 2.5) -> tuple[bool, bool]:
    """Return (reachable, recommended_model_present) without requiring a key."""
    request = Request(base_url.rstrip("/") + "/api/tags", method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, HTTPError, json.JSONDecodeError):
        return False, False

    models = data.get("models", [])
    names = {
        item.get("name")
        for item in models
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    return True, OLLAMA_MODEL in names


def _ollama_status_text(*, reachable: bool, model_present: bool) -> str:
    if not reachable:
        return (
            "Ollama local seleccionado. No necesita una clave API remota. "
            "No detecté Ollama en 127.0.0.1:11434; puedes instalarlo/iniciarlo después."
        )
    if not model_present:
        return (
            "Ollama responde, pero no está instalado el modelo recomendado "
            f"{OLLAMA_MODEL}. Puedes guardarlo y descargar el modelo después."
        )
    return f"✓ Ollama local disponible con {OLLAMA_MODEL}. No se usará una API remota."


def launch_core() -> None:
    if not CORE_EXE.is_file():
        messagebox.showerror("BOT-IA", "No encuentro BOT-IA-Core.exe. La instalación está incompleta.")
        return
    env = os.environ.copy()
    if ENV_PATH.is_file():
        for key, value in _read_env().items():
            env[key] = value
    subprocess.Popen([str(CORE_EXE)], cwd=str(ROOT), env=env)
    raise SystemExit(0)


class SetupWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("BOT-IA — Configuración inicial")
        self.root.geometry("760x520")
        self.root.minsize(680, 480)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.columnconfigure(1, weight=1)

        old = _read_env()
        default_library = Path(old.get("BOT_IA_ONE_NEKO_PUNCH_ROOT", str(ROOT / "biblioteca")))
        self.library = tk.StringVar(value=str(default_library))
        self.provider = tk.StringVar(value=next((name for name, (pid, _) in PROVIDERS.items() if pid == old.get("BOT_IA_PROVIDER")), "OpenAI"))
        selected_key_name = PROVIDERS[self.provider.get()][1]
        self.api_key = tk.StringVar(value=old.get(selected_key_name, "") if selected_key_name else "")
        self.telegram = tk.StringVar(value=old.get("TELEGRAM_BOT_TOKEN", ""))

        outer = ttk.Frame(self.root, padding=24)
        outer.grid(row=0, column=0, columnspan=2, sticky="nsew")
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(5, weight=1)
        ttk.Label(outer, text="BOT-IA", font=("Segoe UI", 24, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(outer, text="Configuración única del equipo", font=("Segoe UI", 12)).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 18))

        ttk.Label(outer, text="Biblioteca de ONE NEKO PUNCH").grid(row=2, column=0, sticky="w", pady=7)
        ttk.Entry(outer, textvariable=self.library).grid(row=2, column=1, sticky="ew", pady=7, padx=10)
        ttk.Button(outer, text="Elegir…", command=self.choose_library).grid(row=2, column=2, pady=7)

        ttk.Label(outer, text="IA principal").grid(row=3, column=0, sticky="w", pady=7)
        combo = ttk.Combobox(outer, textvariable=self.provider, values=tuple(PROVIDERS), state="readonly")
        combo.grid(row=3, column=1, sticky="ew", pady=7, padx=10)
        combo.bind("<<ComboboxSelected>>", self.provider_changed)

        self.key_label = ttk.Label(outer, text="Clave API")
        self.key_label.grid(row=4, column=0, sticky="w", pady=7)
        self.key_entry = ttk.Entry(outer, textvariable=self.api_key, show="•")
        self.key_entry.grid(row=4, column=1, sticky="ew", pady=7, padx=10)

        ttk.Label(outer, text="Telegram (opcional)").grid(row=5, column=0, sticky="nw", pady=7)
        ttk.Entry(outer, textvariable=self.telegram, show="•").grid(row=5, column=1, sticky="new", pady=7, padx=10)

        info = ttk.LabelFrame(outer, text="Comprobación", padding=12)
        info.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(18, 10))
        self.status = ttk.Label(info, text="")
        self.status.pack(anchor="w")

        buttons = ttk.Frame(outer)
        buttons.grid(row=7, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancelar", command=self.root.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Guardar y abrir BOT-IA", command=self.save_and_launch).pack(side="right")
        self.provider_changed()
        self.check_state()

    def choose_library(self) -> None:
        selected = filedialog.askdirectory(title="Selecciona la biblioteca de ONE NEKO PUNCH", initialdir=self.library.get())
        if selected:
            self.library.set(selected)
            self.check_state()

    def provider_changed(self, _event=None) -> None:
        provider = self.provider.get()
        old = _read_env()
        key_name = PROVIDERS[provider][1]
        self.api_key.set(old.get(key_name, "") if key_name else "")
        self.key_entry.configure(state="normal" if key_name else "disabled")
        self.key_label.configure(text="Clave API" if key_name else "Clave API (no requerida)")
        self.check_state()

    def check_state(self) -> None:
        library = Path(self.library.get().strip())
        ok_library = _library_ok(library)
        provider = self.provider.get()
        key_required = bool(PROVIDERS[provider][1])
        key_present = bool(self.api_key.get().strip())
        if not ok_library:
            self.status.configure(text="⚠ Selecciona una carpeta de biblioteca que contenga documentos .md.")
        elif not key_required:
            self.status.configure(text="Ollama local: no requiere clave API remota. Se comprobará al guardar.")
        elif key_present:
            self.status.configure(text="✓ Biblioteca válida y proveedor configurado. Listo para guardar.")
        else:
            self.status.configure(text="⚠ Falta la clave API del proveedor seleccionado.")

    def save_and_launch(self) -> None:
        library = Path(self.library.get().strip()).expanduser()
        if not _library_ok(library):
            messagebox.showwarning("BOT-IA", "La biblioteca indicada no parece contener documentos .md.", parent=self.root)
            return

        provider = self.provider.get()
        key_name = PROVIDERS[provider][1]
        if key_name and not self.api_key.get().strip():
            messagebox.showwarning("BOT-IA", "Introduce la clave API del proveedor seleccionado.", parent=self.root)
            return

        if provider == "Ollama local":
            reachable, model_present = _ollama_probe()
            if not reachable or not model_present:
                detail = _ollama_status_text(reachable=reachable, model_present=model_present)
                proceed = messagebox.askyesno(
                    "BOT-IA — Ollama local",
                    detail + "\n\n¿Quieres guardar igualmente el modo local?",
                    parent=self.root,
                )
                if not proceed:
                    return

        try:
            _write_env(
                universe="one_neko_punch",
                library=library.resolve(),
                provider=provider,
                api_key=self.api_key.get().strip(),
                telegram_token=self.telegram.get().strip(),
            )
            self.root.destroy()
            launch_core()
        except Exception as error:
            messagebox.showerror("BOT-IA", f"No pude guardar la configuración de forma segura:\n{error}", parent=self.root)


def main() -> None:
    env = _read_env()
    if ENV_PATH.is_file() and _library_ok(Path(env.get("BOT_IA_ONE_NEKO_PUNCH_ROOT", str(ROOT / "biblioteca")))) and env.get("BOT_IA_PROVIDER") in {pid for pid, _ in PROVIDERS.values()}:
        try:
            launch_core()
        except SystemExit:
            return
    SetupWindow().root.mainloop()


if __name__ == "__main__":
    main()
