from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent.parent
FROZEN_ROOT = Path(sys.executable).resolve().parent
ROOT = FROZEN_ROOT if getattr(sys, "frozen", False) else SOURCE_ROOT

BOTS = {
    "Cari": ("Cari · Moderación y comunidad", "app.bots.cari", "bots/Cari.exe"),
    "Sunna": ("Sunna · WaifuMon", "app.bots.sunna", "bots/Sunna.exe"),
    "Cami": ("Cami · Analítica y control", "app.bots.cami", "bots/Cami.exe"),
    "Chie": ("Chie · Coordinación y salud", "app.bots.chie", "bots/Chie.exe"),
}


class BotLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bot Manager")
        self.geometry("520x430")
        self.resizable(False, False)
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.buttons: dict[str, tk.Button] = {}

        tk.Label(self, text="BOT MANAGER", font=("Segoe UI", 20, "bold")).pack(pady=(24, 4))
        tk.Label(self, text="Centro de control de las cuatro identidades", font=("Segoe UI", 10)).pack()

        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=36, pady=24)
        for name, (label, _, _) in BOTS.items():
            button = tk.Button(
                frame,
                text=f"Lanzar {name}\n{label.split(' · ', 1)[1]}",
                font=("Segoe UI", 11, "bold"),
                height=3,
                command=lambda bot=name: self.toggle(bot),
            )
            button.pack(fill="x", pady=5)
            self.buttons[name] = button

        tk.Button(self, text="Detener todos", command=self.stop_all).pack(pady=(0, 8))
        self.status = tk.Label(self, text="Estado: listo", anchor="w")
        self.status.pack(fill="x", padx=36, pady=(0, 16))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(1000, self.refresh_status)

    def _command(self, name: str) -> list[str]:
        _, module, executable = BOTS[name]
        if getattr(sys, "frozen", False):
            path = ROOT / executable
            if not path.exists():
                raise FileNotFoundError(
                    f"No existe {path}. Ejecutá tools\\build_launcher.bat para generar los bots."
                )
            return [str(path)]
        return [sys.executable, "-m", module]

    def toggle(self, name: str) -> None:
        process = self.processes.get(name)
        if process is not None and process.poll() is None:
            process.terminate()
            self.status.config(text=f"Estado: {name} detenido")
            return

        try:
            process = subprocess.Popen(
                self._command(name),
                cwd=ROOT,
                env=os.environ.copy(),
                text=True,
            )
        except (OSError, FileNotFoundError) as exc:
            self.status.config(text=f"Error al iniciar {name}: {exc}")
            return

        self.processes[name] = process
        self.status.config(text=f"Estado: {name} iniciado · PID {process.pid}")

    def refresh_status(self) -> None:
        for name, process in list(self.processes.items()):
            if process.poll() is not None:
                self.processes.pop(name, None)
                self.status.config(text=f"Estado: {name} terminó · código {process.returncode}")
        self.after(1000, self.refresh_status)

    def stop_all(self) -> None:
        for process in self.processes.values():
            if process.poll() is None:
                process.terminate()
        self.processes.clear()
        self.status.config(text="Estado: todos detenidos")

    def close(self) -> None:
        self.stop_all()
        self.destroy()


if __name__ == "__main__":
    BotLauncher().mainloop()
