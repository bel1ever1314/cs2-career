"""Repackage reviewed preview ZIPs for an ordinary, unbundled public release.

This tool never discovers sources in a live checkout or player save directory.
Only the exact documentation/tool overlays below are read from project_root.
The frozen backend, engine, artwork and existing license files are retained.
It does not build software, install a game runtime or upload anything.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile


VERSION = "1.7.0-preview.1"
PACKAGE = "CS2Career-" + VERSION
SOURCE_NAME = PACKAGE + "-source.zip"
WINDOWS_NAME = PACKAGE + "-windows.zip"
OVERLAYS = (
    "README.md", "README.en.md", "RELEASE_NOTES.md", "THIRD_PARTY_NOTICES.md",
    "PUBLISHING.md", "docs/3d-preview-packaging.zh-CN.txt",
    "docs/3d-preview-readme.txt", "docs/external-runtime-pins.json",
    "licenses/counter-strike-icons-LICENSE.txt",
    "tools/package_career3d_public.py", "tests/test_package_career3d_public.py",
)
EXCLUDED_SOURCE_PREFIXES = ("third_party/bot-runtime", "legal/bot-runtime")
SOURCE_MANIFEST = "SOURCE_STAGE_MANIFEST.json"
_RESERVED = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)


def _io_path(path: Path) -> Path:
    """Keep Windows long-path handling out of public inventories."""
    path = Path(path)
    if os.name != "nt":
        return path
    value = str(path.absolute())
    if value.startswith("\\\\?\\"):
        return path
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def _stream_digest(stream) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def digest(path: Path) -> str:
    with _io_path(path).open("rb") as stream:
        return _stream_digest(stream)


def _write_json(path: Path, value: dict) -> None:
    _io_path(path).parent.mkdir(parents=True, exist_ok=True)
    _io_path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")


def _key(parts) -> str:
    return unicodedata.normalize("NFC", "/".join(parts)).casefold()


def _archive_entries(archive: zipfile.ZipFile):
    """Validate every entry, including entries later excluded from publication."""
    records, seen, files, root = [], set(), set(), None
    for entry in archive.infolist():
        name = entry.filename
        if entry.orig_filename != name:
            raise ValueError("ZIP filename contains a hidden null byte")
        raw = name[:-1] if entry.is_dir() else name
        parts = raw.split("/")
        if (not raw or "\\" in raw or "\x00" in raw
                or any(not p or p in (".", "..") or ":" in p
                       or p[-1:] in (" ", ".") or _RESERVED.match(p)
                       or any(ord(c) < 32 for c in p) for p in parts)):
            raise ValueError("Unsafe ZIP path")
        kind = stat.S_IFMT(entry.external_attr >> 16)
        if (kind not in (0, stat.S_IFREG, stat.S_IFDIR)
                or entry.external_attr & 0x400 or entry.flag_bits & 1
                or (kind == stat.S_IFDIR and not entry.is_dir())
                or (kind == stat.S_IFREG and entry.is_dir())):
            raise ValueError("ZIP links, special files and encrypted entries are forbidden")
        if root is None:
            root = parts[0]
        if parts[0] != root or (len(parts) == 1 and not entry.is_dir()):
            raise ValueError("ZIP must contain a single enclosing directory")
        key = _key(parts)
        if key in seen:
            raise ValueError("Duplicate or case-colliding ZIP path")
        seen.add(key)
        if not entry.is_dir():
            files.add(key)
        records.append((entry, PurePosixPath(*parts[1:])))
    if not root or not files:
        raise ValueError("ZIP contains no files")
    for entry, relative in records:
        parts = (root, *relative.parts)
        if any(_key(parts[:i]) in files for i in range(1, len(parts))):
            raise ValueError("ZIP file/directory collision")
    return records


def _source_excluded(relative: PurePosixPath) -> bool:
    key = _key(relative.parts)
    return key == SOURCE_MANIFEST.casefold() or any(
        key == prefix or key.startswith(prefix + "/")
        for prefix in EXCLUDED_SOURCE_PREFIXES)


def _validate_runtime(records, archive, source_hash: str) -> None:
    attachments = []
    for entry, relative in records:
        parts = tuple(p.casefold() for p in relative.parts)
        if "mod" in parts or parts[:2] == ("game", "runtime"):
            raise ValueError("Expected an ordinary runtime without mod or game/runtime")
        if parts[:1] == ("source",) and not entry.is_dir():
            if len(parts) != 2 or relative.suffix.casefold() != ".zip":
                raise ValueError("Unexpected runtime source attachment")
            attachments.append(entry)
    if len(attachments) != 1:
        raise ValueError("Runtime must carry exactly one corresponding source ZIP")
    with archive.open(attachments[0]) as stream:
        if _stream_digest(stream) != source_hash:
            raise ValueError("Runtime source attachment does not match the input source ZIP")


def _extract(archive, records, target: Path, excluded) -> None:
    for entry, relative in records:
        # Empty directory entries have no published content, including save/.
        if entry.is_dir() or excluded(relative):
            continue
        destination = _io_path(target.joinpath(*relative.parts))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(entry) as source, destination.open("xb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)


def _overlay_inputs(project_root: Path) -> dict[str, Path]:
    root = project_root.resolve(strict=True)
    inputs = {}
    for relative in OVERLAYS:
        path = root / relative
        for candidate in (path, *path.parents):
            if candidate == root:
                break
            if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
                raise ValueError("Overlay links are forbidden")
        if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
            raise ValueError("Overlay must be an explicit regular project file")
        inputs[relative] = path
    return inputs


def _copy_file(source: Path, destination: Path) -> None:
    _io_path(destination).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_io_path(source), _io_path(destination))


def seal_source_manifest(source: Path, input_hash: str) -> dict:
    files = {
        path.relative_to(_io_path(source)).as_posix(): digest(path)
        for path in sorted(_io_path(source).rglob("*"))
        if path.is_file() and path.relative_to(_io_path(source)).as_posix() != SOURCE_MANIFEST
    }
    report = {
        "schema_version": 1, "version": VERSION,
        "distribution": "ordinary-unbundled", "source_files": len(files),
        "files": files, "input_source_sha256": input_hash,
        "excluded_source_prefixes": list(EXCLUDED_SOURCE_PREFIXES),
        "post_stage_overlays": list(OVERLAYS) + ["3D测试版说明.txt"],
        "live_cs2_test": "pending",
    }
    _write_json(source / SOURCE_MANIFEST, report)
    return report


def _archive(root: Path, destination: Path, prefix: str) -> None:
    with zipfile.ZipFile(_io_path(destination), "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as archive:
        for path in sorted(_io_path(root).rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(_io_path(root)).as_posix()
            entry = zipfile.ZipInfo(prefix + "/" + relative, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            with path.open("rb") as source, archive.open(entry, "w", force_zip64=True) as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)


def repack_public(source_zip: Path, windows_zip: Path, output: Path,
                  project_root: Path) -> dict:
    source_zip, windows_zip = Path(source_zip), Path(windows_zip)
    output = Path(output).absolute()
    if output.exists():
        raise FileExistsError("Choose a new public output directory")
    overlays = _overlay_inputs(Path(project_root))
    input_source = {"sha256": digest(source_zip), "bytes": source_zip.stat().st_size}
    input_windows = {"sha256": digest(windows_zip), "bytes": windows_zip.stat().st_size}
    # Both ZIP inventories are checked before any output tree is created.
    with zipfile.ZipFile(_io_path(source_zip)) as source_archive, \
            zipfile.ZipFile(_io_path(windows_zip)) as runtime_archive:
        source_records = _archive_entries(source_archive)
        runtime_records = _archive_entries(runtime_archive)
        _validate_runtime(runtime_records, runtime_archive, input_source["sha256"])
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".career3d-public-", dir=output.parent))
        try:
            source, runtime = temporary / "source", temporary / "runtime"
            source.mkdir()
            runtime.mkdir()
            _extract(source_archive, source_records, source, _source_excluded)
            _extract(runtime_archive, runtime_records, runtime,
                     lambda relative: relative.parts[:1] and relative.parts[0].casefold() == "source")
            for relative, path in overlays.items():
                _copy_file(path, source / relative)
            readme = source / "docs/3d-preview-readme.txt"
            _copy_file(readme, source / "3D测试版说明.txt")
            source_report = seal_source_manifest(source, input_source["sha256"])
            _archive(source, temporary / SOURCE_NAME, "CS2Career-source")
            _copy_file(temporary / SOURCE_NAME, runtime / "source" / SOURCE_NAME)
            _copy_file(source / "THIRD_PARTY_NOTICES.md", runtime / "THIRD_PARTY_NOTICES.md")
            internal_notice = runtime / "backend/_internal/THIRD_PARTY_NOTICES.md"
            if _io_path(internal_notice).exists():
                _copy_file(source / "THIRD_PARTY_NOTICES.md", internal_notice)
            asset_license = "licenses/counter-strike-icons-LICENSE.txt"
            _copy_file(source / asset_license, runtime / asset_license)
            internal_licenses = runtime / "backend/_internal/licenses"
            if _io_path(internal_licenses).is_dir():
                _copy_file(source / asset_license, internal_licenses / "counter-strike-icons-LICENSE.txt")
            _copy_file(readme, runtime / "测试版说明.txt")
            _archive(runtime, temporary / WINDOWS_NAME, PACKAGE)
            archives = {
                name: {"sha256": digest(temporary / name),
                       "bytes": (temporary / name).stat().st_size}
                for name in (SOURCE_NAME, WINDOWS_NAME)
            }
            manifest = {
                "schema_version": 1, "version": VERSION,
                "distribution": "ordinary-unbundled", "bundled_bot_runtime": False,
                "built_utc": datetime.now(timezone.utc).isoformat(),
                "input_archives": {"source": input_source, "windows": input_windows},
                "archives": archives, "source_files": source_report["source_files"],
                "source_manifest_sha256": digest(source / SOURCE_MANIFEST),
                "live_cs2_test": False, "published_to_github": False,
            }
            _write_json(temporary / "BUILD_MANIFEST.json", manifest)
            (temporary / "SHA256SUMS.txt").write_text("".join(
                row["sha256"] + "  " + name + "\n" for name, row in archives.items()),
                encoding="ascii", newline="\n")
            if output.exists():
                raise FileExistsError("Public output appeared during repackaging")
            temporary.rename(output)
            return manifest
        finally:
            # Only this newly generated and verified sibling staging tree is removed.
            if temporary.exists():
                if not temporary.resolve().is_relative_to(output.parent.resolve()):
                    raise ValueError("Temporary output escaped its parent")
                shutil.rmtree(_io_path(temporary))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--windows-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    report = repack_public(args.source_zip, args.windows_zip, args.output, args.project_root)
    print(json.dumps({"archives": report["archives"], "distribution": report["distribution"]}, indent=2))


if __name__ == "__main__":
    main()
