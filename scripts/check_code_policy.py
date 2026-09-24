# -*- coding: utf-8 -*-
"""Static policy checks for maintained Python source files."""

from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import subprocess
import sys

REQUIRED_HEADER = "# -*- coding: utf-8 -*-"
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "release",
    "__pycache__",
    "experimental",
    "work",
    "tests_backup_langchain",
}
MAINTAINED_ROOTS = ("src", "tests")
MAINTAINED_FILES = (
    "launcher.py",
    "desktop.py",
    "desktop_entry.py",
)


def _iter_all_python_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for base in MAINTAINED_ROOTS:
        directory = root / base
        if not directory.is_dir():
            continue
        paths.extend(
            path
            for path in directory.rglob("*.py")
            if not any(part in EXCLUDED_DIRS for part in path.parts)
        )
    for name in MAINTAINED_FILES:
        path = root / name
        if path.is_file():
            paths.append(path)
    return sorted(set(paths))


def _git_changed_python_files(
    root: Path,
    base: str,
    head: str,
) -> list[Path]:
    zero_sha = "0" * 40
    if not base or base == zero_sha:
        base = f"{head}^"

    completed = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    paths: list[Path] = []
    for value in completed.stdout.splitlines():
        relative = Path(value.strip())
        if (
            relative.suffix.lower() != ".py"
            or not relative.parts
            or any(part in EXCLUDED_DIRS for part in relative.parts)
        ):
            continue
        path = root / relative
        if path.is_file():
            paths.append(path)
    return sorted(set(paths))


def _is_pass_only_exception(handler: ast.ExceptHandler) -> bool:
    if not isinstance(handler.type, ast.Name):
        return False
    if handler.type.id != "Exception":
        return False
    if not handler.body:
        return False
    return all(isinstance(node, ast.Pass) for node in handler.body)


def _check_file(path: Path, root: Path) -> list[str]:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        relative = str(path)
    problems: list[str] = []

    try:
        raw = path.read_bytes()
    except OSError as error:
        return [f"{relative}: cannot read file: {error}"]

    if raw.startswith(bytes.fromhex("efbbbf")):
        problems.append(f"{relative}: UTF-8 BOM is forbidden")

    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        return [f"{relative}: file is not valid UTF-8: {error}"]

    first_line = source.splitlines()[0] if source.splitlines() else ""
    if first_line != REQUIRED_HEADER:
        problems.append(
            f"{relative}: first line must be exactly {REQUIRED_HEADER!r}"
        )

    if "PySide6.Core" in source:
        problems.append(f"{relative}: forbidden import path 'PySide6.Core'")

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        problems.append(
            f"{relative}: syntax error while applying code policy: {error}"
        )
        return problems

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and _is_pass_only_exception(node):
            problems.append(
                f"{relative}:{node.lineno}: 'except Exception: pass' is forbidden"
            )

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enforce BOT-IA Python source policies."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="scan all maintained Python files",
    )
    parser.add_argument(
        "--git-range-env",
        action="store_true",
        help="scan Python files changed between POLICY_BASE and POLICY_HEAD",
    )
    parser.add_argument(
        "--git-range",
        nargs=2,
        metavar=("BASE", "HEAD"),
        help="scan Python files changed between two git refs",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="explicit Python files to scan",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]

    if args.git_range:
        paths = _git_changed_python_files(root, args.git_range[0], args.git_range[1])
    elif args.git_range_env:
        paths = _git_changed_python_files(
            root,
            os.environ.get("POLICY_BASE", ""),
            os.environ.get("POLICY_HEAD", ""),
        )
    elif args.paths:
        paths = []
        for value in args.paths:
            path = value if value.is_absolute() else root / value
            if path.is_file() and path.suffix.lower() == ".py":
                paths.append(path)
        paths = sorted(set(paths))
    else:
        paths = _iter_all_python_files(root)

    if not paths:
        print("Code policy: no maintained Python files to check.")
        return 0

    problems = [
        problem
        for path in paths
        for problem in _check_file(path, root)
    ]

    print(
        f"Code policy: checked {len(paths)} Python file(s); "
        f"violations={len(problems)}."
    )
    for problem in problems:
        print(f"ERROR: {problem}")

    if problems:
        return 1

    print("Code policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
