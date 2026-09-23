from __future__ import annotations

from pathlib import Path
from tkinter import END, Listbox, StringVar, Text, messagebox, ttk

from app.dialogues.models import DialogueEvent, SUPPORTED_IDENTITIES
from app.dialogues.store import DialogueStore


class DialogueEditor(ttk.Frame):
    """Small offline Tk editor for config/dialogues.json used by Bot Manager."""

    def __init__(self, parent, *, store: DialogueStore) -> None:
        super().__init__(parent, padding=14)
        self.store = store
        self.event_var = StringVar()
        self.identity_var = StringVar()
        self._build()
        self.refresh_events()

    def _build(self) -> None:
        selectors = ttk.Frame(self)
        selectors.pack(fill="x", pady=(0, 10))
        ttk.Label(selectors, text="Evento").pack(side="left")
        self.event_box = ttk.Combobox(
            selectors,
            textvariable=self.event_var,
            values=[event.value for event in DialogueEvent],
            state="readonly",
            width=26,
        )
        self.event_box.pack(side="left", padx=(8, 18))
        ttk.Label(selectors, text="Bot").pack(side="left")
        self.identity_box = ttk.Combobox(
            selectors,
            textvariable=self.identity_var,
            values=sorted(SUPPORTED_IDENTITIES),
            state="readonly",
            width=12,
        )
        self.identity_box.pack(side="left", padx=8)
        self.event_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_phrases())
        self.identity_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_phrases())

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self.listbox = Listbox(body, exportselection=False, width=48)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", lambda _event: self.load_selected())

        self.text = Text(body, wrap="word", height=12)
        self.text.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Agregar", command=self.add).pack(side="left")
        ttk.Button(actions, text="Editar seleccionado", command=self.edit).pack(side="left", padx=6)
        ttk.Button(actions, text="Eliminar seleccionado", command=self.delete).pack(side="left")
        ttk.Button(actions, text="Recargar", command=self.refresh_events).pack(side="right")

        self.status = StringVar()
        ttk.Label(self, textvariable=self.status).pack(anchor="w", pady=(8, 0))

    def refresh_events(self) -> None:
        try:
            catalog = self.store.load()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Diálogos", f"No pude cargar el catálogo: {exc}", parent=self.winfo_toplevel())
            return

        keys = sorted(event.value for event in catalog.entries)
        self.event_box["values"] = keys or [event.value for event in DialogueEvent]
        if self.event_var.get() not in self.event_box["values"]:
            self.event_var.set(self.event_box["values"][0] if self.event_box["values"] else "")
        if self.identity_var.get() not in SUPPORTED_IDENTITIES:
            self.identity_var.set("cari")
        self.refresh_phrases()
        self.status.set(f"Archivo: {self.store.path}")

    def refresh_phrases(self) -> None:
        self.listbox.delete(0, END)
        self.text.delete("1.0", END)
        if not self.event_var.get() or not self.identity_var.get():
            return
        try:
            phrases = self.store.load().phrases(self.event_var.get(), self.identity_var.get())
        except (OSError, ValueError) as exc:
            self.status.set(str(exc))
            return
        for index, phrase in enumerate(phrases, start=1):
            self.listbox.insert(END, f"{index:02d} · {phrase}")
        self.status.set(f"{len(phrases)} frase(s)")

    def load_selected(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        phrases = self.store.load().phrases(self.event_var.get(), self.identity_var.get())
        index = selection[0]
        self.text.delete("1.0", END)
        self.text.insert("1.0", phrases[index])

    def _current_text(self) -> str:
        return self.text.get("1.0", END).strip()

    def add(self) -> None:
        text = self._current_text()
        if not text:
            messagebox.showwarning("Diálogos", "Escribí una frase primero.", parent=self.winfo_toplevel())
            return
        try:
            self.store.upsert(self.event_var.get(), self.identity_var.get(), text)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Diálogos", str(exc), parent=self.winfo_toplevel())
            return
        self.refresh_phrases()
        self.status.set("Frase agregada.")

    def edit(self) -> None:
        selection = self.listbox.curselection()
        text = self._current_text()
        if not selection:
            messagebox.showwarning("Diálogos", "Seleccioná una frase.", parent=self.winfo_toplevel())
            return
        if not text:
            messagebox.showwarning("Diálogos", "La frase no puede quedar vacía.", parent=self.winfo_toplevel())
            return
        try:
            self.store.replace(
                self.event_var.get(),
                self.identity_var.get(),
                selection[0],
                text,
            )
        except (OSError, ValueError, IndexError) as exc:
            messagebox.showerror("Diálogos", str(exc), parent=self.winfo_toplevel())
            return
        self.refresh_phrases()
        self.status.set("Frase actualizada.")

    def delete(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Diálogos", "Seleccioná una frase.", parent=self.winfo_toplevel())
            return
        if not messagebox.askyesno(
            "Diálogos",
            "¿Eliminar la frase seleccionada?",
            parent=self.winfo_toplevel(),
        ):
            return
        try:
            self.store.remove(
                self.event_var.get(),
                self.identity_var.get(),
                selection[0],
            )
        except (OSError, ValueError, IndexError) as exc:
            messagebox.showerror("Diálogos", str(exc), parent=self.winfo_toplevel())
            return
        self.refresh_phrases()
        self.status.set("Frase eliminada.")


def open_dialogue_editor(parent, path: str | Path) -> None:
    # Tkinter's Toplevel is imported lazily to keep the module lightweight.
    import tkinter as tk

    window = tk.Toplevel(parent)
    window.title("Casa de Comando — Editor de diálogos")
    window.geometry("1120x680")
    window.minsize(900, 560)
    frame = DialogueEditor(window, store=DialogueStore(path))
    frame.pack(fill="both", expand=True)
    window.transient(parent)
    return None
