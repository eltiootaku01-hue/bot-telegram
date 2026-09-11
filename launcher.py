from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
CORE_EXE = ROOT / "BOT-IA-Core.exe"

PROVIDERS = {
    "OpenAI": ("openai", "OPENAI_API_KEY"),
    "Groq": ("groq", "GROQ_API_KEY"),
    "OpenRouter": ("openrouter", "OPENROUTER_API_KEY"),
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
    key_name = PROVIDERS[provider][1]
    lines = [
        "# BOT-IA generated configuration. This file is local and must never be committed.",
        f"BOT_IA_UNIVERSE={universe}",
        f"BOT_IA_PROVIDER={PROVIDERS[provider][0]}",
        f"BOT_IA_ONE_NEKO_PUNCH_ROOT={library}",
        "",
        f"{key_name}={api_key}",
        "GROQ_API_KEY=" if key_name != "GROQ_API_KEY" else "",
        "OPENAI_API_KEY=" if key_name != "OPENAI_API_KEY" else "",
        "OPENROUTER_API_KEY=" if key_name != "OPENROUTER_API_KEY" else "",
        f"TELEGRAM_BOT_TOKEN={telegram_token}",
    ]
    # Remove empty duplicate provider lines while preserving the selected secret.
    deduped: list[str] = []
    seen = set()
    for line in lines:
        name = line.split("=", 1)[0] if "=" in line else line
        if name in {"OPENAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"}:
            if name in seen:
                continue
            seen.add(name)
        deduped.append(line)
    ENV_PATH.write_text("\n".join(deduped) + "\n", encoding="utf-8")


def _library_ok(path: Path) -> bool:
    return path.is_dir() and any(path.rglob("*.md"))


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
        self.api_key = tk.StringVar(value=old.get(PROVIDERS[self.provider.get()][1], ""))
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

        ttk.Label(outer, text="Clave API").grid(row=4, column=0, sticky="w", pady=7)
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
        self.api_key.set(old.get(PROVIDERS[provider][1], ""))
        self.check_state()

    def check_state(self) -> None:
        library = Path(self.library.get().strip())
        ok_library = _library_ok(library)
        provider = self.provider.get()
        key_required = bool(self.api_key.get().strip())
        if ok_library and key_required:
            self.status.configure(text="✓ Biblioteca válida y proveedor configurado. Listo para guardar.")
        elif not ok_library:
            self.status.configure(text="⚠ Selecciona una carpeta de biblioteca que contenga documentos .md.")
        else:
            self.status.configure(text="⚠ Falta la clave API del proveedor seleccionado.")

    def save_and_launch(self) -> None:
        library = Path(self.library.get().strip()).expanduser()
        if not _library_ok(library):
            messagebox.showwarning("BOT-IA", "La biblioteca indicada no parece contener documentos .md.", parent=self.root)
            return
        if not self.api_key.get().strip():
            messagebox.showwarning("BOT-IA", "Introduce la clave API del proveedor seleccionado.", parent=self.root)
            return
        try:
            _write_env(
                universe="one_neko_punch",
                library=library.resolve(),
                provider=self.provider.get(),
                api_key=self.api_key.get().strip(),
                telegram_token=self.telegram.get().strip(),
            )
            self.root.destroy()
            launch_core()
        except Exception as error:
            messagebox.showerror("BOT-IA", f"No pude guardar la configuración de forma segura:\n{error}", parent=self.root)


def main() -> None:
    if ENV_PATH.is_file() and _library_ok(Path(_read_env().get("BOT_IA_ONE_NEKO_PUNCH_ROOT", str(ROOT / "biblioteca")))) and _read_env().get("BOT_IA_PROVIDER") in {pid for pid, _ in PROVIDERS.values()}:
        try:
            launch_core()
        except SystemExit:
            return
    SetupWindow().root.mainloop()


if __name__ == "__main__":
    main()
