# -*- coding: utf-8 -*-
"""Orquestador asíncrono por prioridad para Café Otaku."""

from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Callable, Dict, Optional


Callback = Callable[[str], Any]
WebWorker = Callable[[str, Dict[str, Any]], Awaitable[str]]


class Priority(IntEnum):
    """Niveles de prioridad del trabajo asíncrono."""

    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass(order=True)
class QueueItem:
    """Elemento ordenable de la cola sin comparar payloads/callbacks."""

    priority: int
    timestamp: float = field(compare=True)
    waitress_id: str = field(compare=False)
    payload: Dict[str, Any] = field(compare=False)
    callback: Optional[Callback] = field(compare=False, default=None)


class CircuitBreaker:
    """Circuit breaker independiente por personaje."""

    def __init__(
        self,
        max_failures: int = 3,
        recovery_time_seconds: float = 30.0,
    ) -> None:
        if max_failures < 1:
            raise ValueError("max_failures debe ser >= 1")
        if recovery_time_seconds < 0:
            raise ValueError("recovery_time_seconds debe ser >= 0")

        self.max_failures = max_failures
        self.recovery_time = recovery_time_seconds
        self.failure_counts: Dict[str, int] = {}
        self.last_failure_time: Dict[str, float] = {}

    def is_open(self, waitress_id: str) -> bool:
        """Indica si el circuito está abierto para la mesera."""
        failures = self.failure_counts.get(waitress_id, 0)

        if failures < self.max_failures:
            return False

        elapsed = time.monotonic() - self.last_failure_time.get(
            waitress_id,
            0.0,
        )

        if elapsed >= self.recovery_time:
            self.failure_counts[waitress_id] = (
                self.max_failures - 1
            )
            return False

        return True

    def record_success(self, waitress_id: str) -> None:
        """Restablece el contador tras una ejecución correcta."""
        self.failure_counts[waitress_id] = 0
        self.last_failure_time.pop(waitress_id, None)

    def record_failure(self, waitress_id: str) -> None:
        """Registra un fallo sin permitir crecimiento innecesario del contador."""
        current = self.failure_counts.get(waitress_id, 0)
        self.failure_counts[waitress_id] = min(
            current + 1,
            self.max_failures,
        )
        self.last_failure_time[waitress_id] = time.monotonic()


class TaskOrchestrator:
    """Cola FIFO por prioridad con timeout y fallback por personaje."""

    WEB_TIMEOUT_SECONDS = 12.0
    POLL_INTERVAL_SECONDS = 0.25

    def __init__(
        self,
        web_worker_callback: WebWorker,
        gui_signal_emitter: Any = None,
    ) -> None:
        if not callable(web_worker_callback):
            raise TypeError("web_worker_callback debe ser invocable")

        self.queue: asyncio.PriorityQueue[QueueItem] = (
            asyncio.PriorityQueue()
        )
        self.circuit_breaker = CircuitBreaker()
        self.web_worker = web_worker_callback
        self.gui_signals = gui_signal_emitter
        self.fallbacks = {
            "cari": (
                "¡Uy! Se me cayó la bandeja... "
                "¿Me repetís lo que necesitabas?"
            ),
            "cami": (
                "Modo de inspección auxiliar activo. "
                "Procesando solicitud en registro local."
            ),
            "sunna": (
                "Las cartas están algo agitadas en este momento. "
                "Reintentemos en breve."
            ),
            "chie": (
                "¡A-ah! Me asusté, dame un segundito "
                "que ordeno los puntos."
            ),
            "chloe": "Bóveda bajo mantenimiento nocturno momentáneo.",
            "scarlet": (
                "La noche está agitada, querido. "
                "Dame un instante para redactar."
            ),
        }
        self._stop_event = asyncio.Event()
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._running = False

    async def enqueue_task(
        self,
        waitress_id: str,
        priority: Priority,
        payload: Dict[str, Any],
        callback: Optional[Callback] = None,
    ) -> bool:
        """Encola trabajo o responde inmediatamente mediante fallback/local."""
        if not isinstance(priority, Priority):
            try:
                priority = Priority(int(priority))
            except (TypeError, ValueError) as error:
                raise ValueError(
                    "priority debe ser Priority.HIGH, MEDIUM o LOW"
                ) from error

        item = QueueItem(
            priority=priority.value,
            timestamp=time.monotonic(),
            waitress_id=waitress_id,
            payload=dict(payload),
            callback=callback,
        )

        if payload.get("is_local_action", False):
            response_text = str(
                payload.get("template_response", "")
            )
            await self._invoke_callback(
                callback,
                response_text,
            )
            return True

        if self.circuit_breaker.is_open(waitress_id):
            fallback_text = self.fallbacks.get(
                waitress_id,
                "Servicio temporalmente en mantenimiento.",
            )
            self._emit_status(
                waitress_id,
                "Modo Auxiliar (Fallback)",
            )
            await self._invoke_callback(
                callback,
                fallback_text,
            )
            return False

        if self._stop_event.is_set():
            await self._invoke_callback(
                callback,
                "El orquestador está detenido temporalmente.",
            )
            return False

        await self.queue.put(item)
        return True

    async def start_worker(self) -> None:
        """Procesa continuamente la cola hasta solicitar shutdown."""
        if self._worker_task is not None:
            if not self._worker_task.done():
                return

        self._stop_event.clear()
        self._running = True
        self._worker_task = asyncio.current_task()

        try:
            while not self._stop_event.is_set():
                try:
                    item = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=self.POLL_INTERVAL_SECONDS,
                    )
                except asyncio.TimeoutError:
                    continue

                try:
                    await self._process_item(item)
                finally:
                    self.queue.task_done()
        except asyncio.CancelledError:
            # stop_worker() uses cancellation for prompt shutdown. Convert
            # that control-flow cancellation into a clean task completion so
            # callers awaiting the worker do not receive CancelledError.
            return
        finally:
            self._running = False
            if (
                self._worker_task is asyncio.current_task()
            ):
                self._worker_task = None

    async def stop_worker(self) -> None:
        """Solicita cierre limpio y cancela el worker si sigue bloqueado."""
        self._stop_event.set()

        task = self._worker_task
        if task is None:
            self._running = False
            return

        if task is asyncio.current_task():
            return

        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._worker_task = None
        self._running = False

    async def drain(self) -> None:
        """Espera hasta procesar todo el trabajo actualmente en cola."""
        await self.queue.join()

    @property
    def is_running(self) -> bool:
        """Indica si el worker de la cola está activo."""
        return self._running

    async def _process_item(self, item: QueueItem) -> None:
        waitress_id = item.waitress_id
        self._emit_status(
            waitress_id,
            "Procesando...",
        )

        try:
            response_text = await asyncio.wait_for(
                self.web_worker(
                    waitress_id,
                    item.payload,
                ),
                timeout=self.WEB_TIMEOUT_SECONDS,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.circuit_breaker.record_failure(waitress_id)
            fallback_text = self.fallbacks.get(
                waitress_id,
                "Respuesta temporal no disponible.",
            )

            status = (
                "Reintentando conexión..."
                if self.circuit_breaker.is_open(waitress_id)
                else "Error puntual"
            )
            self._emit_status(
                waitress_id,
                status,
            )
            await self._invoke_callback(
                item.callback,
                fallback_text,
            )
            return

        self.circuit_breaker.record_success(waitress_id)
        self._emit_status(
            waitress_id,
            "Online",
        )
        await self._invoke_callback(
            item.callback,
            str(response_text),
        )

    async def _invoke_callback(
        self,
        callback: Optional[Callback],
        response_text: str,
    ) -> None:
        if callback is None:
            return

        result = callback(response_text)
        if inspect.isawaitable(result):
            await result

    def _emit_status(
        self,
        waitress_id: str,
        status: str,
    ) -> None:
        emitter = self.gui_signals
        if emitter is None:
            return

        try:
            method = getattr(
                emitter,
                "emit_status_change",
                None,
            )
            if callable(method):
                method(
                    waitress_id,
                    status,
                )
                return

            if callable(emitter):
                emitter(
                    waitress_id,
                    status,
                )
        except Exception:
            # Un fallo de presentación jamás debe bloquear la cola.
            return
