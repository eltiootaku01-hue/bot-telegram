# -*- coding: utf-8 -*-
"""Mutex de proceso para evitar múltiples Telegram pollers por token."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import socket


class TelegramInstanceAlreadyRunning(RuntimeError):
    """Ya existe otro poller de Telegram usando el mismo token."""


class TelegramInstanceLock:
    """Lockfile atómico por token, válido en Windows y POSIX."""

    def __init__(self, token: str, root: str | Path) -> None:
        token = str(token).strip()
        if not token:
            raise ValueError("Telegram token no puede estar vacío")
        self.token_hash = hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()[:32]
        self.path = (
            Path(root).expanduser().resolve()
            / "work"
            / "telegram_poller_locks"
            / f"telegram-{self.token_hash}.lock"
        )
        self._owned = False

    @staticmethod
    def _process_is_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    def _read_owner(self) -> tuple[int, str]:
        try:
            lines = self.path.read_text(
                encoding="utf-8"
            ).splitlines()
        except (OSError, UnicodeDecodeError):
            return 0, ""
        pid = 0
        host = ""
        for line in lines:
            key, _, value = line.partition("=")
            if key == "pid":
                try:
                    pid = int(value)
                except ValueError:
                    pid = 0
            elif key == "host":
                host = value.strip()
        return pid, host

    def _remove_stale_lock(self) -> bool:
        pid, host = self._read_owner()
        if host and host != socket.gethostname():
            return False
        if self._process_is_alive(pid):
            return False
        try:
            self.path.unlink()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return False

    def acquire(self) -> None:
        if self._owned:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            f"pid={os.getpid()}\n"
            f"host={socket.gethostname()}\n"
        )
        for _ in range(2):
            try:
                descriptor = os.open(
                    self.path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                try:
                    os.write(
                        descriptor,
                        payload.encode("utf-8"),
                    )
                finally:
                    os.close(descriptor)
                self._owned = True
                return
            except FileExistsError:
                if not self._remove_stale_lock():
                    raise TelegramInstanceAlreadyRunning(
                        "Ya existe un Telegram poller activo para este token"
                    )
            except OSError as error:
                raise TelegramInstanceAlreadyRunning(
                    "No se pudo adquirir el lock exclusivo del Telegram poller"
                ) from error

        raise TelegramInstanceAlreadyRunning(
            "No se pudo adquirir el lock exclusivo del Telegram poller"
        )

    def release(self) -> None:
        if not self._owned:
            return
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        finally:
            self._owned = False

    def __enter__(self) -> "TelegramInstanceLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
