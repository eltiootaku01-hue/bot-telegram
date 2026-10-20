# -*- coding: utf-8 -*-
"""Fail-safe resource policy for the BOT-IA desktop process tree.

The GUI samples the sensor; worker processes read the latest atomic state file.
Missing or stale measurements are never interpreted as zero.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, replace
from enum import IntEnum
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Callable

MIN_BUDGET_BYTES = 1_000_000_000
MAX_BUDGET_BYTES = 2_000_000_000
BUDGET_STEP_BYTES = 250_000_000
SCHEMA_VERSION = 1
RUNTIME_STALE_SECONDS = 5.0
SAMPLE_INTERVAL_SECONDS = 1.0
WARNING_FRACTION = 0.85
GAMES_PRESSURE_FRACTION = 0.95
PRESSURE_FRACTION = 1.00
CRITICAL_FRACTION = 1.10
CRITICAL_RECOVERY_FRACTION = 0.90
PRESSURE_RECOVERY_FRACTION = 0.80
WARNING_RECOVERY_FRACTION = 0.75
RECOVERY_SECONDS = 10


class TaskPriority(IntEnum):
    P0_MODERATION = 0
    P1_CRITICAL = 1
    P2_ORDINARY = 2
    P3_GAMES = 3
    P4_BACKGROUND = 4


class PressureLevel(IntEnum):
    UNKNOWN = -1
    NORMAL = 0
    WARNING = 1
    GAMES_PAUSED = 2
    REDUCING = 3
    CRITICAL = 4


PROFILE_NAMES = {
    1_000_000_000: "MODERACIÓN PRIORITARIA",
    1_250_000_000: "MODERACIÓN + FUNCIONES ESENCIALES",
    1_500_000_000: "TRABAJO CONTROLADO",
    1_750_000_000: "ACTIVIDAD AMPLIADA",
    2_000_000_000: "PRESUPUESTO MÁXIMO",
}


def validate_budget_bytes(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("budget_bytes must be an integer")
    if not MIN_BUDGET_BYTES <= value <= MAX_BUDGET_BYTES:
        raise ValueError("budget_bytes must be between 1 and 2 decimal GB")
    if (value - MIN_BUDGET_BYTES) % BUDGET_STEP_BYTES:
        raise ValueError("budget_bytes must use 0.25 GB steps")
    return value


def profile_name(budget_bytes: int) -> str:
    return PROFILE_NAMES[validate_budget_bytes(budget_bytes)]


def default_preferences_path() -> Path:
    """Keep preferences in per-user local data, not in the installation tree."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "BOT-IA" / "resource_governor.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / "BOT-IA" / "resource_governor.json"


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    valid: bool
    working_set_bytes: int | None = None
    private_commit_bytes: int | None = None
    process_count: int | None = None
    reason: str = ""

    @classmethod
    def invalid(cls, reason: str) -> "MemorySnapshot":
        return cls(False, None, None, None, reason)


@dataclass(frozen=True, slots=True)
class GovernorSnapshot:
    budget_bytes: int
    pressure: PressureLevel
    memory: MemorySnapshot
    peak_working_set_bytes: int | None
    sampled_at: float
    preference_saved: bool
    configuration_recovered: bool
    runtime_state_saved: bool = True

    @property
    def status_label(self) -> str:
        if not self.memory.valid or self.pressure is PressureLevel.UNKNOWN:
            return "PRESUPUESTO NO VERIFICADO"
        if (self.memory.working_set_bytes or 0) > self.budget_bytes:
            return "PRESUPUESTO SUPERADO"
        if self.pressure in {
            PressureLevel.WARNING,
            PressureLevel.GAMES_PAUSED,
            PressureLevel.REDUCING,
            PressureLevel.CRITICAL,
        }:
            return "REDUCIENDO CARGA"
        return "DENTRO DEL PRESUPUESTO"

    @property
    def paused_categories(self) -> tuple[str, ...]:
        if not self.memory.valid or self.pressure is PressureLevel.UNKNOWN:
            return (
                "interacciones ordinarias",
                "juegos",
                "trabajo de fondo y navegación pesada",
            )
        paused: list[str] = []
        if self.budget_bytes < 1_500_000_000:
            paused.append("juegos")
        if self.budget_bytes < 1_750_000_000 or self.pressure in {
            PressureLevel.WARNING,
            PressureLevel.GAMES_PAUSED,
            PressureLevel.REDUCING,
            PressureLevel.CRITICAL,
        }:
            paused.append("trabajo de fondo y navegación pesada")
        if self.pressure in {
            PressureLevel.GAMES_PAUSED,
            PressureLevel.REDUCING,
            PressureLevel.CRITICAL,
        } and "juegos" not in paused:
            paused.append("juegos")
        if self.pressure in {PressureLevel.REDUCING, PressureLevel.CRITICAL}:
            paused.insert(0, "interacciones ordinarias")
        return tuple(paused)


@dataclass(frozen=True, slots=True)
class PreferenceLoad:
    budget_bytes: int
    present: bool
    recovered: bool


class ResourcePreferenceStore:
    """Atomic, secret-free user preference and latest sample storage."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_preferences_path()

    def load_preferences(self) -> PreferenceLoad:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return PreferenceLoad(MIN_BUDGET_BYTES, False, False)
        except (OSError, ValueError, TypeError):
            return PreferenceLoad(MIN_BUDGET_BYTES, True, True)
        try:
            if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("unsupported schema")
            return PreferenceLoad(validate_budget_bytes(payload.get("budget_bytes")), True, False)
        except (ValueError, TypeError):
            return PreferenceLoad(MIN_BUDGET_BYTES, True, True)

    def save_budget(self, budget_bytes: int) -> bool:
        validate_budget_bytes(budget_bytes)
        runtime = None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("runtime"), dict):
                runtime = payload["runtime"]
        except (OSError, ValueError, TypeError):
            pass
        payload = {"schema_version": SCHEMA_VERSION, "budget_bytes": budget_bytes}
        if runtime is not None:
            payload["runtime"] = runtime
        return self._atomic_write(payload)

    def publish_runtime(self, snapshot: GovernorSnapshot) -> bool:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "budget_bytes": snapshot.budget_bytes,
            "runtime": {
                "sampled_at": snapshot.sampled_at,
                "valid": snapshot.memory.valid,
                "reason": snapshot.memory.reason[:160],
                "pressure": snapshot.pressure.name,
                "status_label": snapshot.status_label,
                "working_set_bytes": snapshot.memory.working_set_bytes,
                "private_commit_bytes": snapshot.memory.private_commit_bytes,
                "process_count": snapshot.memory.process_count,
                "peak_working_set_bytes": snapshot.peak_working_set_bytes,
                "paused_categories": list(snapshot.paused_categories),
                "preference_saved": snapshot.preference_saved,
            },
        }
        return self._atomic_write(payload)

    def allows_priority(self, priority: TaskPriority, *, now: float | None = None) -> bool | None:
        """Read worker policy. None means the GUI has never activated this feature."""
        priority = TaskPriority(priority)
        if priority in {TaskPriority.P0_MODERATION, TaskPriority.P1_CRITICAL}:
            return True
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError):
            return False
        if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
            return False
        runtime = payload.get("runtime")
        if not isinstance(runtime, dict):
            return False
        try:
            sampled_at = float(runtime.get("sampled_at"))
            budget = validate_budget_bytes(payload.get("budget_bytes"))
            pressure = PressureLevel[str(runtime.get("pressure"))]
            valid = runtime.get("valid") is True
            working_set = runtime.get("working_set_bytes")
        except (ValueError, TypeError, KeyError):
            return False
        current = time.time() if now is None else now
        if sampled_at <= 0 or current - sampled_at > RUNTIME_STALE_SECONDS or sampled_at > current + 2:
            return False
        if not valid or not isinstance(working_set, int) or isinstance(working_set, bool) or working_set < 0:
            return False
        if pressure is PressureLevel.UNKNOWN or working_set > budget:
            return False
        if pressure in {PressureLevel.REDUCING, PressureLevel.CRITICAL}:
            return False
        if priority is TaskPriority.P2_ORDINARY:
            return True
        if priority is TaskPriority.P3_GAMES:
            return (
                pressure is not PressureLevel.GAMES_PAUSED
                and budget >= 1_500_000_000
            )
        if priority is TaskPriority.P4_BACKGROUND:
            return (
                pressure is PressureLevel.NORMAL
                and budget >= 1_750_000_000
            )
        return False

    def secondary_comments_allowed(self, *, now: float | None = None) -> bool:
        return self.allows_priority(TaskPriority.P2_ORDINARY, now=now) is not False

    def _atomic_write(self, payload: dict[str, object]) -> bool:
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=f".{self.path.name}.", suffix=".tmp", delete=False,
            ) as handle:
                temporary = handle.name
                json.dump(payload, handle, ensure_ascii=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            return True
        except (OSError, ValueError, TypeError):
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
            return False


class WindowsProcessTreeSampler:
    """Sum working sets for the current process and descendants; commit is diagnostic."""
    TH32CS_SNAPPROCESS = 0x00000002
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_VM_READ = 0x0010

    def __init__(self, root_pid: int | None = None) -> None:
        self.root_pid = int(root_pid if root_pid is not None else os.getpid())

    def sample(self) -> MemorySnapshot:
        if os.name != "nt":
            return MemorySnapshot.invalid("La medición completa del árbol requiere Windows")
        try:
            return self._sample_windows()
        except (OSError, AttributeError, TypeError, ValueError) as error:
            return MemorySnapshot.invalid(f"Fallo de medición Windows: {type(error).__name__}")

    def _sample_windows(self) -> MemorySnapshot:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
            ]

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.Process32FirstW.restype = wintypes.BOOL
        kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.Process32NextW.restype = wintypes.BOOL
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

        handle = kernel32.CreateToolhelp32Snapshot(self.TH32CS_SNAPPROCESS, 0)
        invalid_handle = ctypes.c_void_p(-1).value
        if not handle or ctypes.cast(handle, ctypes.c_void_p).value == invalid_handle:
            raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
        processes: dict[int, int] = {}
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        try:
            if not kernel32.Process32FirstW(handle, ctypes.byref(entry)):
                raise OSError(ctypes.get_last_error(), "Process32FirstW failed")
            while True:
                processes[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
                if not kernel32.Process32NextW(handle, ctypes.byref(entry)):
                    error_code = ctypes.get_last_error()
                    if error_code != 18:  # ERROR_NO_MORE_FILES
                        raise OSError(error_code, "Process32NextW failed")
                    break
        finally:
            kernel32.CloseHandle(handle)
        if self.root_pid not in processes:
            return MemorySnapshot.invalid("El proceso raíz no aparece en el inventario Windows")

        children: dict[int, list[int]] = {}
        for pid, parent in processes.items():
            children.setdefault(parent, []).append(pid)
        pids: list[int] = []
        pending, seen = [self.root_pid], set()
        while pending:
            pid = pending.pop()
            if pid in seen:
                continue
            seen.add(pid)
            pids.append(pid)
            pending.extend(children.get(pid, ()))

        working_set = private_commit = 0
        for pid in pids:
            process = kernel32.OpenProcess(
                self.PROCESS_QUERY_LIMITED_INFORMATION | self.PROCESS_VM_READ, False, pid,
            )
            if not process:
                return MemorySnapshot.invalid(f"No se pudo medir el proceso descendiente PID {pid}")
            counters = PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(counters)
            try:
                if not psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
                    return MemorySnapshot.invalid(f"No se pudo leer memoria del proceso PID {pid}")
                working_set += int(counters.WorkingSetSize)
                private_commit += int(counters.PrivateUsage)
            finally:
                kernel32.CloseHandle(process)
        if not pids:
            return MemorySnapshot.invalid("El inventario de memoria quedó vacío")
        return MemorySnapshot(True, working_set, private_commit, len(pids), "")


class ResourceGovernor:
    """Policy controller. The GUI calls sample() approximately once per second."""
    def __init__(
        self,
        *,
        store: ResourcePreferenceStore | None = None,
        sampler: object | None = None,
        root_pid: int | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.store = store or ResourcePreferenceStore()
        self.sampler = sampler or WindowsProcessTreeSampler(root_pid)
        self._clock = clock
        loaded = self.store.load_preferences()
        self._budget_bytes = loaded.budget_bytes
        self.configuration_recovered = loaded.recovered
        self.preference_saved = loaded.present and not loaded.recovered
        if loaded.recovered or not loaded.present:
            self.preference_saved = self.store.save_budget(MIN_BUDGET_BYTES)
        self._pressure = PressureLevel.UNKNOWN
        self._last_memory = MemorySnapshot.invalid("Todavía no hay una muestra válida")
        self._peak_working_set_bytes: int | None = None
        self._recovery_count = 0
        self._last_snapshot = GovernorSnapshot(
            self._budget_bytes, self._pressure, self._last_memory, None,
            self._clock(), self.preference_saved, self.configuration_recovered,
        )
        self._publish_snapshot()

    @property
    def budget_bytes(self) -> int:
        return self._budget_bytes

    @property
    def snapshot(self) -> GovernorSnapshot:
        return self._last_snapshot

    def _publish_snapshot(self) -> None:
        published = self.store.publish_runtime(self._last_snapshot)
        self._last_snapshot = replace(self._last_snapshot, runtime_state_saved=published)

    def set_budget_bytes(self, value: int) -> bool:
        self._budget_bytes = validate_budget_bytes(value)
        self.preference_saved = self.store.save_budget(value)
        self._recovery_count = 0
        self._last_snapshot = GovernorSnapshot(
            self._budget_bytes, PressureLevel.UNKNOWN,
            MemorySnapshot.invalid("El presupuesto cambió; esperando nueva muestra"),
            self._peak_working_set_bytes, self._clock(), self.preference_saved,
            self.configuration_recovered,
        )
        self._publish_snapshot()
        return self.preference_saved

    def sample(self) -> GovernorSnapshot:
        try:
            memory = self.sampler.sample()
        except Exception as error:
            memory = MemorySnapshot.invalid(f"Fallo de sensor: {type(error).__name__}")
        if not isinstance(memory, MemorySnapshot) or not memory.valid:
            reason = memory.reason if isinstance(memory, MemorySnapshot) else "El sensor devolvió un formato inválido"
            self._last_memory = MemorySnapshot.invalid(reason or "Medición no válida")
            self._pressure = PressureLevel.UNKNOWN
            self._recovery_count = 0
        elif memory.working_set_bytes is None or memory.working_set_bytes < 0:
            self._last_memory = MemorySnapshot.invalid("El sensor no entregó working set válido")
            self._pressure = PressureLevel.UNKNOWN
            self._recovery_count = 0
        else:
            self._last_memory = memory
            ws = memory.working_set_bytes
            self._peak_working_set_bytes = max(ws, self._peak_working_set_bytes or ws)
            self._advance_pressure(ws)
        self._last_snapshot = GovernorSnapshot(
            self._budget_bytes, self._pressure, self._last_memory,
            self._peak_working_set_bytes, self._clock(), self.preference_saved,
            self.configuration_recovered,
        )
        self._publish_snapshot()
        return self._last_snapshot

    def _advance_pressure(self, working_set_bytes: int) -> None:
        ratio, current = working_set_bytes / self._budget_bytes, self._pressure
        # Escalate immediately; recover one level only after ten stable samples.
        if current is PressureLevel.CRITICAL:
            if ratio <= CRITICAL_RECOVERY_FRACTION:
                self._recovery_count += 1
                if self._recovery_count >= RECOVERY_SECONDS:
                    self._pressure, self._recovery_count = PressureLevel.REDUCING, 0
            else:
                self._recovery_count = 0
            return
        if ratio >= CRITICAL_FRACTION:
            self._pressure, self._recovery_count = PressureLevel.CRITICAL, 0
            return
        if current is PressureLevel.REDUCING:
            if ratio <= PRESSURE_RECOVERY_FRACTION:
                self._recovery_count += 1
                if self._recovery_count >= RECOVERY_SECONDS:
                    self._pressure, self._recovery_count = PressureLevel.GAMES_PAUSED, 0
            else:
                self._recovery_count = 0
            return
        if ratio >= PRESSURE_FRACTION:
            self._pressure, self._recovery_count = PressureLevel.REDUCING, 0
            return
        if current is PressureLevel.GAMES_PAUSED:
            if ratio <= WARNING_RECOVERY_FRACTION:
                self._recovery_count += 1
                if self._recovery_count >= RECOVERY_SECONDS:
                    self._pressure, self._recovery_count = PressureLevel.WARNING, 0
            else:
                self._recovery_count = 0
            return
        if ratio >= GAMES_PRESSURE_FRACTION:
            self._pressure, self._recovery_count = PressureLevel.GAMES_PAUSED, 0
            return
        if current is PressureLevel.WARNING:
            if ratio <= WARNING_RECOVERY_FRACTION:
                self._recovery_count += 1
                if self._recovery_count >= RECOVERY_SECONDS:
                    self._pressure, self._recovery_count = PressureLevel.NORMAL, 0
            else:
                self._recovery_count = 0
            return
        self._pressure = PressureLevel.WARNING if ratio >= WARNING_FRACTION else PressureLevel.NORMAL
        self._recovery_count = 0

    def allows(self, priority: TaskPriority) -> bool:
        priority = TaskPriority(priority)
        if priority in {TaskPriority.P0_MODERATION, TaskPriority.P1_CRITICAL}:
            return True
        if not self._last_memory.valid or self._pressure is PressureLevel.UNKNOWN:
            return False
        if self._pressure in {PressureLevel.REDUCING, PressureLevel.CRITICAL}:
            return False
        if priority is TaskPriority.P2_ORDINARY:
            return True
        if priority is TaskPriority.P3_GAMES:
            return (
                self._pressure is not PressureLevel.GAMES_PAUSED
                and self._budget_bytes >= 1_500_000_000
            )
        if priority is TaskPriority.P4_BACKGROUND:
            return (
                self._pressure is PressureLevel.NORMAL
                and self._budget_bytes >= 1_750_000_000
            )
        return False

    def denial_reason(self, priority: TaskPriority) -> str:
        priority = TaskPriority(priority)
        if priority in {TaskPriority.P0_MODERATION, TaskPriority.P1_CRITICAL}:
            return "La política conserva P0/P1 en todos los perfiles"
        if not self._last_memory.valid or self._pressure is PressureLevel.UNKNOWN:
            return "PRESUPUESTO NO VERIFICADO: no se admiten nuevas tareas secundarias"
        if self._pressure in {PressureLevel.CRITICAL, PressureLevel.REDUCING} or (
            self._last_memory.working_set_bytes is not None
            and self._last_memory.working_set_bytes > self._budget_bytes
        ):
            return "PRESUPUESTO SUPERADO: se conservan solo moderación y funciones críticas"
        if self._pressure is PressureLevel.GAMES_PAUSED:
            return "REDUCIENDO CARGA: juegos y tareas de fondo están pausados"
        if self._pressure is PressureLevel.WARNING and priority is TaskPriority.P4_BACKGROUND:
            return "REDUCIENDO CARGA: trabajo de fondo y navegación pesada están pausados"
        if priority is TaskPriority.P3_GAMES and self._budget_bytes < 1_500_000_000:
            return "El perfil actual mantiene pausados los juegos"
        if priority is TaskPriority.P4_BACKGROUND and self._budget_bytes < 1_750_000_000:
            return "El perfil actual mantiene pausado el trabajo pesado"
        return "La categoría está limitada por la política del recurso"
