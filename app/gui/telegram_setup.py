from __future__ import annotations

import tkinter as tk
import webbrowser
from threading import Thread
from tkinter import messagebox, ttk

from app.services.telegram_setup import (
    TelegramBotIdentity,
    TelegramChatCheck,
    build_group_add_link,
    build_private_link,
    check_bot_in_chat,
    required_group_rights,
    verify_bot_token,
)


class TelegramSetupAssistant(tk.Toplevel):
    """Guided Telegram setup window used by the desktop Bot Manager."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        bots: dict[str, tuple[str, str, str, str]],
        bot_vars: dict[str, dict[str, tk.StringVar]],
        authorized_chats_var: tk.StringVar,
        base_group_var: tk.StringVar,
    ) -> None:
        super().__init__(parent)
        self.title("Asistente de Telegram — Bot Manager")
        self.geometry("980x720")
        self.minsize(900, 650)
        self.transient(parent)
        self.grab_set()

        self.bots = bots
        self.bot_vars = bot_vars
        self.authorized_chats_var = authorized_chats_var
        self.base_group_var = base_group_var
        self.meta: dict[str, TelegramBotIdentity] = {}
        self.status_vars: dict[str, tk.StringVar] = {}
        self.group_vars: dict[str, tk.StringVar] = {}

        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="ASISTENTE DE INSTALACIÓN TELEGRAM",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text="✓ listo · ⚠ requiere atención · ✗ bloqueado. Chie es el grupo base.",
        ).pack(anchor="w", pady=(2, 14))

        base = ttk.LabelFrame(outer, text="Grupo general / bienvenida", padding=12)
        base.pack(fill="x", pady=(0, 12))
        ttk.Label(base, text="ID del grupo base").grid(row=0, column=0, sticky="w")
        ttk.Entry(base, textvariable=self.base_group_var, width=22).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Button(base, text="Revisar grupo base", command=self.review_group).grid(row=0, column=2, padx=6)
        ttk.Button(base, text="Autorizar este grupo", command=self.authorize_base_group).grid(row=0, column=3, padx=6)
        self.group_state_var = tk.StringVar(value="⚠ todavía no revisado")
        ttk.Label(base, textvariable=self.group_state_var).grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(
            base,
            text="Chie debe estar presente como administradora con permisos de temas, eliminación y restricción.",
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))

        bots = ttk.LabelFrame(outer, text="Identidad y entrada de cada bot", padding=12)
        bots.pack(fill="both", expand=True)
        headings = ("Bot", "Estado", "Identidad Telegram", "Acciones")
        for column, heading in enumerate(headings):
            ttk.Label(bots, text=heading, font=("Segoe UI", 9, "bold")).grid(
                row=0, column=column, sticky="w", padx=5, pady=(0, 8)
            )
        bots.columnconfigure(1, weight=1)
        bots.columnconfigure(2, weight=1)

        for row, (key, (label, role, _, _)) in enumerate(self.bots.items(), start=1):
            ttk.Label(bots, text=f"{label}\n{role}").grid(row=row, column=0, sticky="w", padx=5, pady=8)
            status = tk.StringVar(value="⚠ sin verificar")
            self.status_vars[key] = status
            ttk.Label(bots, textvariable=status).grid(row=row, column=1, sticky="w", padx=5, pady=8)
            identity = tk.StringVar(value="—")
            self.group_vars[key] = identity
            ttk.Label(bots, textvariable=identity).grid(row=row, column=2, sticky="w", padx=5, pady=8)
            actions = ttk.Frame(bots)
            actions.grid(row=row, column=3, sticky="e", padx=5, pady=8)
            ttk.Button(actions, text="Verificar", command=lambda name=key: self.verify_one(name)).pack(side="left", padx=3)
            ttk.Button(actions, text="Abrir chat", command=lambda name=key: self.open_private(name)).pack(side="left", padx=3)
            ttk.Button(actions, text="Agregar al grupo", command=lambda name=key: self.add_to_group(name)).pack(side="left", padx=3)

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(12, 0))
        ttk.Button(controls, text="Verificar todos", command=self.verify_all).pack(side="left")
        ttk.Button(controls, text="Revisar presencia en grupo", command=self.review_group).pack(side="left", padx=8)
        ttk.Button(controls, text="Manual de Telegram", command=self.show_manual).pack(side="right")

    def _token(self, key: str) -> str:
        return self.bot_vars[key]["token"].get().strip()

    def verify_one(self, key: str) -> None:
        self.status_vars[key].set("… consultando Telegram")
        Thread(target=self._verify_worker, args=(key,), daemon=True, name=f"telegram-verify-{key}").start()

    def _verify_worker(self, key: str) -> None:
        result = verify_bot_token(self._token(key))
        self.after(0, lambda: self._apply_identity(key, result))

    def _apply_identity(self, key: str, result: TelegramBotIdentity) -> None:
        self.meta[key] = result
        if not result.configured:
            self.status_vars[key].set("✗ falta token")
            self.group_vars[key].set("—")
            return
        if not result.ok:
            self.status_vars[key].set("✗ token rechazado")
            self.group_vars[key].set(result.error)
            return

        username = f"@{result.username}" if result.username else "(sin username)"
        self.status_vars[key].set("✓ token válido")
        self.group_vars[key].set(f"{result.first_name} · {username}")
        if result.username:
            self.bot_vars[key]["link"].set(build_private_link(result.username))

    def verify_all(self) -> None:
        for key in self.bots:
            self.verify_one(key)

    def add_to_group(self, key: str) -> None:
        result = self.meta.get(key)
        if result is None or not result.ok or not result.username:
            self.verify_one(key)
            messagebox.showinfo(
                "Agregar bot",
                "Primero se verifica el token. Volvé a pulsar «Agregar al grupo» cuando aparezca ✓.",
                parent=self,
            )
            return
        url = build_group_add_link(result.username, role=key)
        webbrowser.open(url)
        self.status_vars[key].set("⚠ Telegram abierto: elegí el grupo y aceptá la incorporación")

    def open_private(self, key: str) -> None:
        result = self.meta.get(key)
        if result is None or not result.ok or not result.username:
            self.verify_one(key)
            return
        webbrowser.open(build_private_link(result.username))

    def authorize_base_group(self) -> None:
        raw = self.base_group_var.get().strip()
        try:
            group_id = int(raw)
        except ValueError:
            self.group_state_var.set("✗ ID de grupo inválido")
            return
        existing = [item.strip() for item in self.authorized_chats_var.get().split(",") if item.strip()]
        if str(group_id) not in existing:
            existing.append(str(group_id))
        self.authorized_chats_var.set(",".join(existing))
        self.group_state_var.set("✓ grupo agregado a AUTHORIZED_CHAT_IDS")

    def review_group(self) -> None:
        try:
            group_id = int(self.base_group_var.get().strip())
        except ValueError:
            self.group_state_var.set("✗ falta un ID numérico de grupo base")
            return
        if group_id >= 0:
            self.group_state_var.set("✗ el ID de un grupo/supergrupo debe ser negativo")
            return
        self.group_state_var.set("… comprobando grupo y presencia de los bots")
        Thread(
            target=self._review_worker,
            args=(group_id,),
            daemon=True,
            name="telegram-group-review",
        ).start()

    def _review_worker(self, group_id: int) -> None:
        results: dict[str, TelegramChatCheck | None] = {}
        for key in self.bots:
            token = self._token(key)
            if not token:
                results[key] = None
                continue
            results[key] = check_bot_in_chat(
                token,
                group_id,
                required_rights=required_group_rights(key),
            )
        self.after(0, lambda: self._apply_group_review(group_id, results))

    def _apply_group_review(
        self,
        group_id: int,
        results: dict[str, TelegramChatCheck | None],
    ) -> None:
        chie = results.get("chie")
        if chie is not None and chie.chat_type not in {"group", "supergroup"}:
            self.group_state_var.set(
                f"✗ el chat base es de tipo {chie.chat_type or 'desconocido'}; elegí un grupo/supergrupo"
            )
            return
        if chie is None:
            state = "✗ Chie no tiene token configurado"
        elif not chie.ok:
            details = chie.error or "Chie no está correctamente instalada"
            if chie.missing_rights:
                details += " · faltan: " + ", ".join(chie.missing_rights)
            state = f"✗ Chie: {details}"
        else:
            state = f"✓ Chie presente · {chie.title or group_id} · {chie.bot_status}"
            if chie.missing_rights:
                state += " · ⚠ faltan permisos: " + ", ".join(chie.missing_rights)

        others = []
        for key, result in results.items():
            if key == "chie":
                continue
            if result is None:
                others.append(f"⚠ {key.title()}: sin token")
            elif result.ok:
                rights = ""
                if result.missing_rights:
                    rights = " · ⚠ " + ", ".join(result.missing_rights)
                others.append(f"✓ {key.title()}: {result.bot_status}{rights}")
            else:
                error = result.error or "no presente"
                if result.missing_rights:
                    error += " · ⚠ " + ", ".join(result.missing_rights)
                others.append(f"✗ {key.title()}: {error}")

        self.group_state_var.set(state + (" | " + " · ".join(others) if others else ""))

    def show_manual(self) -> None:
        manual = (
            "1. Creá los cuatro bots con @BotFather y copiá cada token.\n"
            "2. Verificá cada token aquí. Si es correcto, el Manager obtiene el @username.\n"
            "3. Agregá primero Chie al grupo general usando «Agregar al grupo».\n"
            "4. En el grupo ejecutá /configurar con Chie. Ella comprobará permisos y creará los temas.\n"
            "5. Copiá el ID negativo del grupo base a esta pantalla y autorizalo.\n"
            "6. Agregá Cari, Sunna y Cami usando sus botones.\n"
            "7. Volvé a «Revisar presencia en grupo» hasta que Chie tenga ✓ y los demás estén presentes.\n"
            "8. Guardá la configuración y usá «Comenzar».\n\n"
            "Importante: Telegram no permite que este programa fuerce la incorporación del bot sin tu acción.\n"
            "El botón «Agregar al grupo» abre el selector oficial de Telegram."
        )
        messagebox.showinfo("Manual rápido de Telegram", manual, parent=self)
