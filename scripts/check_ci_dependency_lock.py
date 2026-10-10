# -*- coding: utf-8 -*-
"""Validate the committed CI dependency lock without rewriting it."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys
import tomllib

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[1]
PROJECT_FILE = ROOT / "pyproject.toml"
LOCK_FILE = ROOT / "requirements-ci.lock"
TARGETS = (
    ("linux", "Linux"),
    ("win32", "Windows"),
)


def _environment(sys_platform: str, platform_system: str) -> dict[str, str]:
    environment = default_environment()
    environment.update(
        python_version="3.14",
        python_full_version="3.14.8",
        sys_platform=sys_platform,
        platform_system=platform_system,
        os_name="nt" if sys_platform == "win32" else "posix",
        implementation_name="cpython",
        platform_python_implementation="CPython",
    )
    return environment


def _load_lock() -> list[Requirement]:
    if not LOCK_FILE.is_file():
        raise ValueError(f"required lockfile is missing: {LOCK_FILE.name}")

    requirements: list[Requirement] = []
    for line_number, raw_line in enumerate(
        LOCK_FILE.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        specifiers = list(requirement.specifier)
        if (
            requirement.url is not None
            or len(specifiers) != 1
            or specifiers[0].operator != "=="
            or specifiers[0].version.endswith(".*")
        ):
            raise ValueError(
                f"{LOCK_FILE.name}:{line_number} is not an exact version pin: {line}"
            )
        requirements.append(requirement)
    return requirements


def main() -> int:
    project = tomllib.loads(PROJECT_FILE.read_text(encoding="utf-8"))
    lock = _load_lock()
    direct_requirements = [
        *project["project"].get("dependencies", []),
        *project.get("dependency-groups", {}).get("test", []),
    ]

    for sys_platform, platform_system in TARGETS:
        environment = _environment(sys_platform, platform_system)
        active_lock: dict[str, Requirement] = {}
        for requirement in lock:
            if requirement.marker and not requirement.marker.evaluate(
                environment=environment
            ):
                continue
            name = canonicalize_name(requirement.name)
            if name in active_lock:
                raise ValueError(
                    f"duplicate active lock entries for {requirement.name} on {sys_platform}"
                )
            active_lock[name] = requirement

        for raw_requirement in direct_requirements:
            requirement = Requirement(raw_requirement)
            if requirement.marker and not requirement.marker.evaluate(
                environment=environment
            ):
                continue
            name = canonicalize_name(requirement.name)
            locked = active_lock.get(name)
            if locked is None:
                raise ValueError(
                    f"{requirement.name} is missing from {LOCK_FILE.name} for {sys_platform}"
                )
            locked_version = Version(next(iter(locked.specifier)).version)
            if not requirement.specifier.contains(
                locked_version,
                prereleases=True,
            ):
                declared = str(requirement.specifier) or "any version"
                raise ValueError(
                    f"{requirement.name} requirement {declared} in pyproject.toml "
                    f"does not allow the pinned version {locked_version} in {LOCK_FILE.name}"
                )

    active_environment = default_environment()
    for requirement in lock:
        if requirement.marker and not requirement.marker.evaluate(
            environment=active_environment
        ):
            continue
        locked_version = Version(next(iter(requirement.specifier)).version)
        try:
            installed_version = Version(version(requirement.name))
        except PackageNotFoundError as error:
            raise ValueError(
                f"locked dependency is not installed: {requirement.name}"
            ) from error
        if installed_version != locked_version:
            raise ValueError(
                f"installed {requirement.name}={installed_version}; "
                f"{LOCK_FILE.name} requires {locked_version}"
            )

    print(
        f"dependency lock verified: {len(lock)} exact pins; "
        "direct dependencies match pyproject.toml for Python 3.14 on Linux and Windows"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, tomllib.TOMLDecodeError, ValueError) as error:
        print(f"dependency lock verification failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
