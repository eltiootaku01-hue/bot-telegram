from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox


ROOT = Path(__file__).resolve().parent.parent

BOTS = {
    "Cari": ("Cari · Moderación y comunidad", "app.bots.cari"),
    "Sunna": ("Sunna · WaifuMon", "app.bots.sunna"),
    "Cami": ("Cami · Analítica y control", "app.bots.cami"),
    "Chie": ("Chie · Coordinación y salud", "app.bots.chie"),
}


class BotLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bot Manager")
        self.geometry("520x430")
        self.resizable(False, False)
        self.processes: dict[str, subprocess.Popen[str]] = {}

        tk.Label(self, text="BOT MANAGER", font=("Segoe UI", 20, "bold")).pack(pady=(24, 4))
        tk.Label(self, text="Centro de control de las cuatro identidades", font=("Segoe UI", 10)).pack()

        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=36, pady=24)
        for name, (label, _) in BOTS.items():
            tk.Button(
                frame,
                text=f"Lanzar {name}\n{label.split(' · ', 1)[1]}",
                font=("Segoe UI", 11, "bold"),
                height=3,
                command=lambda bot=name: self.toggle(bot),
            ).pack(fill="x", pady=5)

        tk.Button(self, text="Detener todos", command=self.stop_all).pack(pady=(0, 8))
        self.status = tk.Label(self, text="Estado: listo", anchor="w")
        self.status.pack(fill="x", padx=36, pady=(0, 16))
        self.protocol("WM_DELETE_WINDOW", self.close)

    def toggle(self, name: str) -> None:
        process = self.processes.get(name)
        if process is not None and process.poll() is None:
            process.terminate()
            self.status.config(text=f"Estado: {name} detenido")
            return
        module = BOTS[name][1]
        env = os.environ.copy()
        process = subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=ROOT,
            env=env,
            text=True,
        )
        self.processes[name] = process
        self.status.config(text=f"Estado: {name} iniciado · PID {process.pid}")

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
