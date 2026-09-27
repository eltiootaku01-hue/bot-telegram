# -*- coding: utf-8 -*-
"""Instrumentacion reversible para el forense de KeyboardInterrupt en FASE 1J."""
from __future__ import annotations

import json
import os
import platform
import sys
import threading
import time
import traceback
from pathlib import Path


ARTIFACT_DIR = Path("phase1j-artifacts")
ARTIFACT_PATH = ARTIFACT_DIR / "keyboardinterrupt-forensics.json"


class Phase1JRecorder:
    def __init__(self) -> None:
        self.started = time.monotonic()
        self.events: list[dict[str, object]] = []
        self._installed = False
        self._originals: list[tuple[object, str, object]] = []

    def log(self, event: str, **details: object) -> None:
        self.events.append({
            "t_monotonic": time.monotonic(),
            "t_delta": time.monotonic() - self.started,
            "event": event,
            **details,
        })

    @staticmethod
    def _thread_info(thread: threading.Thread | None) -> dict[str, object]:
        if thread is None:
            return {}
        return {
            "name": thread.name,
            "ident": thread.ident,
            "native_id": getattr(thread, "native_id", None),
            "daemon": thread.daemon,
            "alive": thread.is_alive(),
        }

    def _snapshot(self, current: threading.Thread | None = None) -> dict[str, object]:
        frames = sys._current_frames()
        current = current or threading.current_thread()
        threads = []
        for thread in threading.enumerate():
            frame = frames.get(thread.ident)
            threads.append({
                **self._thread_info(thread),
                "stack": "".join(traceback.format_stack(frame)) if frame else "",
            })
        return {
            "pid": os.getpid(),
            "python": sys.version,
            "python_implementation": platform.python_implementation(),
            "pytest": self._pytest_version(),
            "platform": platform.platform(),
            "windows_version": platform.version() if sys.platform == "win32" else None,
            "hostname": platform.node(),
            "current_thread": self._thread_info(current),
            "threads": threads,
        }

    @staticmethod
    def _pytest_version() -> str | None:
        try:
            import pytest
            return str(pytest.__version__)
        except Exception:
            return None

    def capture_keyboard_interrupt(self, error: BaseException, *, tracker=None) -> None:
        snapshot = self._snapshot()
        self.log(
            "keyboard_interrupt",
            exception_type=type(error).__name__,
            exception_message=str(error),
            traceback="".join(traceback.format_exception(type(error), error, error.__traceback__)),
            **snapshot,
            tracker_state=self._tracker_state(tracker),
        )
        self._write_artifact(snapshot, tracker)

    @staticmethod
    def _tracker_state(tracker) -> dict[str, object]:
        if tracker is None:
            return {}
        stop_event = getattr(tracker, "_stop", None)
        started_event = None
        thread = getattr(tracker, "_thread", None)
        if thread is not None:
            started_event = getattr(thread, "_started", None)
        return {
            "tracker_type": type(tracker).__name__,
            "stop_set": bool(stop_event.is_set()) if stop_event is not None else None,
            "thread": Phase1JRecorder._thread_info(thread),
            "started_event_set": bool(started_event.is_set()) if started_event is not None else None,
            "thread_starting": bool(getattr(thread, "_started", None) is not None and not getattr(thread, "_started").is_set()) if thread is not None else None,
        }

    def _write_artifact(self, snapshot: dict[str, object], tracker) -> None:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "phase": "1J",
            "events": self.events,
            "snapshot": snapshot,
            "tracker_state": self._tracker_state(tracker),
        }
        ARTIFACT_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def install(self, tracker, adapter) -> None:
        if self._installed:
            return
        self._installed = True
        self.log("test_started")

        self._wrap_method(tracker, "_ensure_writer_started", "tracker.ensure_writer_started")
        self._wrap_method(tracker, "record_message", "tracker.record_message")
        self._wrap_method(tracker, "_writer", "writer.entry", thread_target=True)
        self._wrap_method(tracker, "stop", "tracker.stop")
        self._wrap_method(adapter, "close", "adapter.close")

        original_start = threading.Thread.start
        recorder = self

        def start(thread, *args, **kwargs):
            recorder.log("thread_start_called", thread=recorder._thread_info(thread))
            started = getattr(thread, "_started", None)
            if started is not None:
                original_wait = started.wait

                def wait(*wargs, **wkwargs):
                    recorder.log("thread_started_wait_enter", thread=recorder._thread_info(thread))
                    try:
                        result = original_wait(*wargs, **wkwargs)
                    except BaseException as error:
                        recorder.log(
                            "thread_started_wait_exception",
                            thread=recorder._thread_info(thread),
                            exception_type=type(error).__name__,
                            exception_message=str(error),
                        )
                        raise
                    recorder.log("thread_started_wait_return", thread=recorder._thread_info(thread))
                    return result

                started.wait = wait
            try:
                result = original_start(thread, *args, **kwargs)
            except BaseException as error:
                recorder.log(
                    "thread_start_exception",
                    thread=recorder._thread_info(thread),
                    exception_type=type(error).__name__,
                    exception_message=str(error),
                )
                raise
            recorder.log("thread_start_return", thread=recorder._thread_info(thread))
            return result

        threading.Thread.start = start
        self._originals.append((threading.Thread, "start", original_start))

        original_join = threading.Thread.join

        def join(thread, *args, **kwargs):
            recorder.log(
                "thread_join_called",
                thread=recorder._thread_info(thread),
                timeout=args[0] if args else kwargs.get("timeout"),
            )
            try:
                result = original_join(thread, *args, **kwargs)
            except BaseException as error:
                recorder.log(
                    "thread_join_exception",
                    thread=recorder._thread_info(thread),
                    exception_type=type(error).__name__,
                    exception_message=str(error),
                )
                raise
            recorder.log("thread_join_return", thread=recorder._thread_info(thread))
            return result

        threading.Thread.join = join
        self._originals.append((threading.Thread, "join", original_join))

        original_kill = os.kill

        def kill(pid, sig):
            recorder.log("os.kill_call", pid=pid, signal=sig)
            try:
                result = original_kill(pid, sig)
            except BaseException as error:
                recorder.log(
                    "os.kill_exception",
                    pid=pid,
                    signal=sig,
                    exception_type=type(error).__name__,
                    exception_message=str(error),
                )
                raise
            recorder.log("os.kill_return", pid=pid, signal=sig)
            return result

        os.kill = kill
        self._originals.append((os, "kill", original_kill))

        try:
            from bot_ia.interfaces.telegram_instance_lock import TelegramInstanceLock
            original_alive = TelegramInstanceLock._process_is_alive

            def process_is_alive(lock, pid):
                recorder.log("telegram_instance_lock.process_is_alive_enter", pid=pid)
                try:
                    result = original_alive(lock, pid)
                except BaseException as error:
                    recorder.log(
                        "telegram_instance_lock.process_is_alive_exception",
                        pid=pid,
                        exception_type=type(error).__name__,
                        exception_message=str(error),
                    )
                    raise
                recorder.log(
                    "telegram_instance_lock.process_is_alive_return",
                    pid=pid,
                    result=result,
                )
                return result

            TelegramInstanceLock._process_is_alive = process_is_alive
            self._originals.append((TelegramInstanceLock, "_process_is_alive", original_alive))
        except (AttributeError, ImportError):
            self.log("telegram_instance_lock_instrumentation_unavailable")

    def _wrap_method(self, obj, name: str, event: str, *, thread_target: bool = False) -> None:
        original = getattr(obj, name)
        recorder = self

        def wrapper(*args, **kwargs):
            recorder.log(event + "_enter", thread=recorder._thread_info(threading.current_thread()))
            try:
                result = original(*args, **kwargs)
            except BaseException as error:
                recorder.log(
                    event + "_exception",
                    thread=recorder._thread_info(threading.current_thread()),
                    exception_type=type(error).__name__,
                    exception_message=str(error),
                )
                raise
            recorder.log(event + "_return", thread=recorder._thread_info(threading.current_thread()))
            return result

        setattr(obj, name, wrapper)
        self._originals.append((obj, name, original))

    def uninstall(self) -> None:
        for obj, name, original in reversed(self._originals):
            setattr(obj, name, original)
        self._originals.clear()
        self._installed = False
