from __future__ import annotations

import argparse
import json
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

DEFAULT_MANIFEST = "scavenger_manifest.json"
USER_AGENT = "WaifuMon-Scavenger/1.0"
CHUNK_SIZE = 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 60
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024


class ScavengerError(RuntimeError):
    pass


def _safe_member_path(target_dir: Path, member_name: str) -> Path:
    """Reject absolute paths and path traversal inside ZIP archives."""
    normalized = PurePosixPath(member_name.replace("\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ScavengerError(f"Unsafe ZIP member path: {member_name!r}")

    destination = (target_dir / Path(*normalized.parts)).resolve()
    target_root = target_dir.resolve()
    if destination != target_root and target_root not in destination.parents:
        raise ScavengerError(f"ZIP member escapes target directory: {member_name!r}")
    return destination


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _download_to_temp(url: str, destination_dir: Path, *, timeout: int) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/zip,application/octet-stream,*/*"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise ScavengerError(f"HTTP {status} while downloading {url}")

        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                declared = int(content_length)
            except ValueError as exc:
                raise ScavengerError(f"Invalid Content-Length from {url}") from exc
            if declared > MAX_DOWNLOAD_BYTES:
                raise ScavengerError(
                    f"Download exceeds {MAX_DOWNLOAD_BYTES} bytes: {declared}"
                )

        with tempfile.NamedTemporaryFile(
            prefix=".scavenger-",
            suffix=".zip",
            dir=destination_dir,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            total = 0
            try:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise ScavengerError(
                            f"Download exceeds {MAX_DOWNLOAD_BYTES} bytes: {url}"
                        )
                    temporary.write(chunk)
            except Exception:
                temporary_path.unlink(missing_ok=True)
                raise

    if total == 0:
        temporary_path.unlink(missing_ok=True)
        raise ScavengerError(f"Empty download: {url}")
    return temporary_path


def _extract_zip(zip_path: Path, target_dir: Path) -> int:
    extracted = 0
    with zipfile.ZipFile(zip_path, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ScavengerError(f"Corrupt ZIP member: {bad_member}")

        members = archive.infolist()
        for info in members:
            if _is_symlink(info):
                raise ScavengerError(f"Symlink ZIP member is not permitted: {info.filename}")

            destination = _safe_member_path(target_dir, info.filename)
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, destination.open("wb") as output:
                while True:
                    chunk = source.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
            extracted += 1
    return extracted


def fetch_item(item: dict, *, dry_run: bool = False, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> int:
    required = ("name", "category", "url", "target_dir")
    missing = [key for key in required if not item.get(key)]
    if missing:
        raise ScavengerError(f"Manifest item missing required fields: {', '.join(missing)}")

    if item.get("license_verified") is not True:
        raise ScavengerError(
            f"License gate refused automatic download for {item['name']}: "
            "license_verified must be true"
        )

    target_dir = Path(item["target_dir"])
    print(f"\n[SAQUEANDO] {item['name']} ({item['category']})")
    print(f"[FUENTE] {item.get('source_url', item['url'])}")
    print(f"[DESCARGA] {item['url']}")
    print(f"[DESTINO] {target_dir}")

    if dry_run:
        return 0

    temporary_zip = _download_to_temp(item["url"], target_dir, timeout=timeout)
    try:
        count = _extract_zip(temporary_zip, target_dir)
    finally:
        temporary_zip.unlink(missing_ok=True)

    print(f"[OK] {item['name']}: {count} archivos extraídos.")
    return count


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ScavengerError(f"No se encontró {path}") from exc
    except json.JSONDecodeError as exc:
        raise ScavengerError(f"JSON inválido en {path}: {exc}") from exc

    downloads = data.get("downloads")
    if not isinstance(downloads, list):
        raise ScavengerError("El campo 'downloads' debe ser una lista.")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="WaifuMon Scavenger asset fetcher")
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST,
        help=f"Ruta del manifiesto (default: {DEFAULT_MANIFEST})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Muestra qué se descargaría sin tocar archivos.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Timeout HTTP por descarga (default: {DEFAULT_TIMEOUT_SECONDS}s)",
    )
    args = parser.parse_args()

    manifest = load_manifest(Path(args.manifest))
    total_files = 0
    failures = 0

    print("=== PROTOCOLO SCAVENGER: EXTRACCIÓN CONTROLADA DE ASSETS ===")
    for item in manifest["downloads"]:
        try:
            total_files += fetch_item(item, dry_run=args.dry_run, timeout=args.timeout)
        except Exception as exc:
            failures += 1
            print(f"[FALLO] {item.get('name', '<sin nombre>')}: {exc}")

    print(
        f"\n=== FINAL: {'sin fallos' if failures == 0 else f'{failures} fallo(s)'}; "
        f"{total_files} archivo(s) extraído(s). ==="
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
