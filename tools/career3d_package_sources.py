"""Stage the public 3D source tree without walking a player's runtime folder.

The stage is a new directory published only after validation succeeds. Original
files are never edited. Machine home paths in text are replaced with the public
Windows placeholder; binary resources fail closed instead of being rewritten.
The manifest records every copied file and every transformation, without the
developer's absolute source paths. The release packager owns ZIP creation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import tempfile
from typing import Mapping


VERSION = "1.7.0-preview.1"
PROJECT = "work/career3d_redesign"
RTS_PROJECT = "work/career_rts"
DEFAULT_ASSET_ROOT = Path("E:/CS2CareerTools/Career3DRedesign/assets")
DEFAULT_FONT_ROOT = Path("E:/CS2CareerTools/Career3DMedia/fonts")
MODEL_NAMES = ("cozy_room.glb", "chicken_club.glb", "player_chicken.glb", "major_walk.glb")
FONT_HASHES = {
    "ChillRoundF.ttf": "ebeb471ae9778a26012a18136f8a9ae99450832cd8bb259265684720d60839f0",
    "OFL.txt": "d45891f8adfd21368c98e803603df1f575ff3fc4a6ec713ba7ccf0e3cba15b28",
}
DLLS = frozenset({
    "vendor/CareerMatch/CareerMatch.dll", "vendor/BotBuy/BotBuy.dll",
    "vendor/InvsimCareer/InvsimCareer.dll",
    "vendor/InventorySimulator/plugins/InventorySimulator/InventorySimulator.dll",
})
ROOT_FILES = frozenset({
    "README.md", "README.en.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "RECOVERED_SOURCE.md", "RELEASE_NOTES.md", "PUBLISHING.md",
    "DEVELOPER_GUIDE.zh-CN.md", "EXTENSION_ARCHITECTURE.zh-CN.md",
    "CS2_INTEGRATION.zh-CN.md", "DESKTOP_REBUILD_STATUS.zh-CN.md",
    "V1.6.0_GUIDE.md", "ENGLISH_LOCALIZATION.md", ".gitignore",
    "requirements-desktop.txt", "main.py", "preview_main.py", "playtest_main.py", "career3d_backend_main.py",
    "build_desktop_preview.py", "build_exe.py", "开始游玩-FAQ.txt",
    "剧情扩展说明.txt", "本队路径与界面平滑说明.txt", "自动模拟和辅助设置说明.txt",
    "助攻与场内对话说明.txt", "比分观赛和Major赛制说明.txt", "自己改剧情和打包.txt",
})
TEXT_SUFFIXES = frozenset({
    ".py", ".cs", ".csproj", ".js", ".cjs", ".css", ".html", ".json",
    ".md", ".txt", ".svg", ".ps1", ".cmd", ".gd", ".uid", ".tscn",
    ".godot", ".gdshader", ".gdshaderinc", ".cfg", ".toml", ".yml", ".yaml",
})
BINARY_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".db"})
SPECIAL_TEXT_NAMES = frozenset({"LICENSE", "NOTICE", ".gitignore", ".gdignore"})
PRIVATE_DIRS = frozenset({
    ".git", ".agents", ".codex", ".cursor", ".vscode", ".godot", ".desktop-deps",
    "__pycache__", "bin", "obj", "node_modules", "save", "saves", "runtime",
    "runtime-temp", "temp", "tmp", "build", "dist", "release", "publish", "cache",
    "caches", "logs", "reports", "tests-output", "test-output", "source-snapshots",
    "snapshots", "backups", "runtime-cache", "install-backups", "captures", "renders", "exports", "demo", "demos",
    "demodata", "natural_behavior", "botlab", "cs2botlab", "local-actions-probe",
    "localactionsprobe", "localactionslab", "local_actions", "view_angle_lab",
})
PRIVATE_SUFFIXES = frozenset({".dem", ".parquet", ".pdb", ".pyc", ".pyo", ".log", ".import", ".blend1", ".tmp", ".lock"})
PRIVATE_FILENAMES = frozenset({
    "career.json", "season.json", "cs2.json", "owner.txt", ".career3d-demo.json",
    ".career3d-start.json", ".service.lock", "ready.json",
})
TOOL_FILES = frozenset({
    "build_plugins.ps1", "build_skin_art.py", "build_team_avatars.py",
    "build_inspect_catalog.py", "run_tests.py", "Launch-CS2Career.cmd",
    "sync_career_rts.ps1", "deploy_career_rts.ps1", "deploy_career3d_redesign.ps1",
    "godot_source_snapshots.gdignore", "transfer_ui_fixture.py", "career_matrix.py",
    "flow_evidence.py", "compare_player_flows.py", "playthrough.py",
})
TOOL_TEST_DIRS = ("tools/identity-tests", "tools/botbuy-tests", "tools/tactical-tests")
PRIVATE_HOME = re.compile(
    r"(?P<drive>[A-Z]:)(?P<separator>[/\\]+)Users[/\\]+(?P<user>[^/\\\s\"'<>]+)", re.I)
CREDENTIAL = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{32,}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
EXTERNAL_AUTHORING_SOURCES = {
    PROJECT + "/source/build_chicken.py": Path("E:/CS2CareerTools/ChickenCharacterPrototype/source/build_chicken.py"),
    PROJECT + "/source/build_grand_arena.py": Path("E:/CS2CareerTools/GrandMajorArenaPrototype/source/build_grand_arena.py"),
    PROJECT + "/source/small_arena_reference.py": Path("E:/CS2CareerTools/GrandMajorArenaPrototype/source/small_arena_reference.py"),
    "licenses/GeneralUser-GS-LICENSE.txt": Path("E:/CS2CareerTools/AudioTools/GeneralUser-GS-LICENSE.txt"),
}
AUDIO_NAMES = frozenset({"arena_entrance.ogg", "arena_entrance.wav", "arena_entrance.mid", "arena_entrance_composition.json", "README.md"})


def _io_path(path: Path) -> Path:
    """Use Windows extended paths only for I/O, never for public inventories."""
    path = Path(path)
    if os.name != "nt":
        return path
    value = str(path.absolute())
    if value.startswith("\\\\?\\"):
        return Path(value)
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with _io_path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def excluded_path(relative: Path | PurePosixPath | str) -> bool:
    parts = PurePosixPath(str(relative).replace("\\", "/")).parts
    if not parts:
        return False
    # Runtime license records are source/legal inputs, not writable game state.
    # Keep this exception narrow; every ordinary game/project runtime is excluded.
    return (any((p.casefold() in PRIVATE_DIRS and not (
        p.casefold() == "runtime" and index > 0 and parts[index - 1].casefold() == "licenses"))
        or p.casefold().startswith((".qa", ".work-", ".botlab", ".staging-", "service-"))
        for index, p in enumerate(parts))
        or PurePosixPath(parts[-1]).suffix.casefold() in PRIVATE_SUFFIXES
        or parts[-1].casefold() in PRIVATE_FILENAMES)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def _check_file(path: Path, relative: str, root: Path | None = None) -> None:
    if _is_link(path):
        raise ValueError("Linked public source is forbidden: " + relative)
    for parent in path.parents:
        if _is_link(parent):
            raise ValueError("Linked public source ancestor is forbidden: " + relative)
        if root is not None and parent == root:
            break
    if not path.is_file() or (root is not None and not path.resolve().is_relative_to(root)):
        raise ValueError("Missing or outside-root public source: " + relative)


def _walk(root: Path, relative_dir: str, allowed: frozenset[str] | None = None) -> list[Path]:
    folder = root / relative_dir
    if _is_link(folder):
        raise ValueError("Linked source directory is forbidden: " + relative_dir)
    if not folder.exists():
        return []
    selected = []
    for current, dirs, files in os.walk(folder, followlinks=False):
        current = Path(current)
        for dirname in list(dirs):
            path = current / dirname
            rel = path.relative_to(root).as_posix()
            if excluded_path(rel):
                dirs.remove(dirname)
            elif _is_link(path):
                raise ValueError("Linked source directory is forbidden: " + rel)
        for filename in files:
            path = current / filename
            rel = path.relative_to(root).as_posix()
            if excluded_path(rel):
                continue
            suffix = path.suffix.casefold()
            if suffix == ".dll":
                include = rel in DLLS
            elif allowed is not None:
                include = suffix in allowed or path.name in SPECIAL_TEXT_NAMES
            else:
                include = suffix in TEXT_SUFFIXES | BINARY_SUFFIXES or path.name in SPECIAL_TEXT_NAMES
            if include:
                _check_file(path, rel, root)
                selected.append(path)
    return selected


def source_files(root: Path) -> list[Path]:
    """Return only in-workspace source inputs; external models/fonts are separate."""
    if _is_link(Path(root)):
        raise ValueError("The source root cannot be a link")
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("The source root is not a directory")
    selected = []
    for name in sorted(ROOT_FILES):
        path = root / name
        if path.exists() or _is_link(path):
            _check_file(path, name, root)
            selected.append(path)
    for folder in ("cs2career", "tests", "licenses", "docs", "extensions/_templates",
                   "vendor/CareerMatch", "vendor/BotBuy", "vendor/InvsimCareer", "vendor/InventorySimulator",
                   *TOOL_TEST_DIRS):
        selected.extend(_walk(root, folder))
    extension_readme = root / "extensions/README.md"
    if extension_readme.exists():
        _check_file(extension_readme, "extensions/README.md", root)
        selected.append(extension_readme)
    for path in sorted((root / "tools").glob("*")):
        name = path.name
        include = name in TOOL_FILES or (path.suffix == ".py" and name.startswith(
            ("career3d_", "verify_career3d_", "prepare_career3d_", "package_career3d", "build_career3d")))
        include = include or (path.suffix == ".cjs" and name.startswith("test_")) or name == "package_public.py"
        if include and not excluded_path(path.relative_to(root)):
            _check_file(path, path.relative_to(root).as_posix(), root)
            selected.append(path)
    godot_types = frozenset({".gd", ".uid", ".tscn", ".godot", ".gdshader", ".gdshaderinc", ".json", ".txt", ".md", ".py", ".cs", ".csproj", ".png"})
    for project in (PROJECT, RTS_PROJECT):
        project_root = root / project
        if _is_link(project_root):
            raise ValueError("Linked project directory is forbidden: " + project)
        for path in sorted(project_root.glob("*")):
            if path.is_dir():
                continue
            if path.suffix.casefold() in {".gd", ".uid", ".tscn", ".godot", ".txt", ".md", ".cmd"} or path.name in SPECIAL_TEXT_NAMES:
                _check_file(path, path.relative_to(root).as_posix(), root)
                selected.append(path)
        for folder in ("scripts", "data", "source", "tests", "scenes"):
            selected.extend(_walk(root, project + "/" + folder, godot_types))
        if project == RTS_PROJECT:
            selected.extend(_walk(root, project + "/assets", frozenset({".png", ".txt", ".md", ".json"})))
            selected.extend(_walk(root, project + "/tools", godot_types))
        else:
            for folder in ("scripts", "data", "assets"):
                selected.extend(_walk(root, project + "/rts/" + folder, godot_types))
    return sorted(set(selected), key=lambda p: p.relative_to(root).as_posix())


def verify_public_text(text: str, relative: str = "public source") -> None:
    if CREDENTIAL.search(text):
        raise ValueError("Possible credential in public source: " + relative)
    if any(m.group("user").casefold() not in {"public", "default"} for m in PRIVATE_HOME.finditer(text)):
        raise ValueError("Private Windows home path in public source: " + relative)


def _portable_home(text: str) -> tuple[str, int]:
    count = 0
    def replace(match):
        nonlocal count
        if match.group("user").casefold() in {"public", "default"}:
            return match.group(0)
        count += 1
        return match.group("drive") + match.group("separator") + "Users" + match.group("separator") + "Public"
    return PRIVATE_HOME.sub(replace, text), count


def _verify_binary(path: Path, relative: str) -> None:
    tail = b""
    with _io_path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            verify_public_text((tail + block).decode("utf-8", errors="replace"), relative)
            tail = block[-1024:]


def _verify_glb(path: Path, relative: str) -> None:
    with _io_path(path).open("rb") as stream:
        header = stream.read(12)
    if len(header) != 12 or struct.unpack("<4sII", header) != (b"glTF", 2, _io_path(path).stat().st_size):
        raise ValueError("Expected a complete GLB 2.0 model: " + relative)


def _extra_target(relative: str) -> str:
    path = PurePosixPath(relative.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts or ":" in path.parts[0] or excluded_path(path):
        raise ValueError("Unsafe additional source destination")
    target = path.as_posix()
    prefixes = ("tools/", "licenses/", "docs/", PROJECT + "/source/", PROJECT + "/assets/")
    if not target.startswith(prefixes):
        raise ValueError("Additional sources must be explicit tools, licenses, docs or original 3D assets/source")
    if path.suffix.casefold() not in TEXT_SUFFIXES | {".blend", ".glb", ".ogg", ".wav", ".mid"} and path.name not in SPECIAL_TEXT_NAMES:
        raise ValueError("Unsupported additional source type: " + target)
    if path.suffix == ".dll":
        raise ValueError("Additional DLLs are forbidden")
    return target


def _launcher(project: str) -> str:
    return '\n'.join([
        "@echo off", "setlocal", "rem Supply CS2CAREER_GODOT or place Godot.exe in the source tree tools/godot folder.",
        'if not defined CS2CAREER_GODOT set "CS2CAREER_GODOT=%~dp0..\\..\\tools\\godot\\Godot.exe"',
        'if not exist "%CS2CAREER_GODOT%" (', "    echo Set CS2CAREER_GODOT to your Godot 4 executable.",
        "    pause", "    exit /b 1", ")", 'if not exist "%~dp0runtime" mkdir "%~dp0runtime"',
        'start "" "%CS2CAREER_GODOT%" --path "%~dp0." --log-file "%~dp0runtime\\godot.log"',
        "endlocal", "exit /b 0", "",
    ])


BUILD_GUIDE = """# Public 3D source stage

This tree contains the Python career engine, Godot 3D client, canonical standalone
RTS source and its namespaced client copy. It contains no player save, runtime,
private extension, original Demo, cached account data or previous source snapshot.

Install Python 3.12+ and requirements-desktop.txt for the original desktop build.
The 3D backend uses the Python career source at the root of this tree. Install
Godot 4, set CS2CAREER_GODOT to its executable, and use
work/career3d_redesign/启动样板.cmd. data/career_link.json uses python on PATH
and a project-relative repo_root. Select an explicit Python in that config if
needed. Runtime data is created inside the project's runtime/career directory.
The standalone RTS launcher uses the same Godot environment variable.

Optional image media is separate: put locally prepared assets under media/ at
the source-tree root, with teams/team-media.json, maps/ and skin_art/. Manifest
image paths are relative to their own manifest. Missing media stays a placeholder.
Valve artwork and team trademarks are not licensed as project code. Preparation
scripts and provenance references are included; player image caches are excluded.
ChillRoundF.ttf and fonts/OFL.txt are copied only after pinned SHA256 checks.

Original models can be regenerated with Blender from source/:
1. room_primitives_reference.py exports cozy_room.glb.
2. build_chicken.py exports rookie_chicken.glb and rookie_chicken.blend; copy
   them to assets/player_chicken.glb and assets/chicken_source.blend. The shipped
   player/chicken-source files are identical to these original authoring outputs.
3. build_club.py consumes chicken_source.blend and exports chicken_club.glb.
4. build_grand_arena.py plus small_arena_reference.py create grand_major_arena.blend;
   build_walkable_arena.py consumes it locally and exports major_walk.glb.
Music source is compose_arena_entrance.py; GeneralUser GS rendering attribution
and its original license are retained when the rendered music is included.
Generated soundfont/tools/installer distributions are not copied by this stage.
RTS map rebuilding uses numpy/Pillow plus the explicitly supplied local NAV input;
the nav_export project declares its .NET SDK and ValveResourceFormat dependency.

SOURCE_STAGE_MANIFEST.json records public source hashes and transformations.
Machine Windows home prefixes in text are changed to C:/Users/Public (preserving
the original slash style); credential-like text and private paths in binaries
are rejected. The source inputs themselves are never rewritten. Configuration
and launchers in this stage use portable source settings. Game verification
remains pending; source/isolated tests do not certify a live CS2 match.
"""


def stage_sources(root: Path, destination: Path, asset_root: Path | None = None,
                  font_root: Path | None = None, extra_sources: Mapping[str, Path] | None = None,
                  *, version: str = VERSION, include_external_authoring: bool = True) -> dict:
    """Validate and atomically copy a reproducible, sanitized public source tree.

    extra_sources maps an explicit archive-relative destination to one file. It
    never walks external directories. Existing output is never overwritten.
    """
    original_root, destination_input = Path(root), Path(destination)
    if _is_link(original_root) or _is_link(destination_input):
        raise ValueError("Source/output directory links are forbidden")
    root, destination = original_root.resolve(), destination_input.resolve()
    if not re.fullmatch(r"[A-Za-z0-9.-]+", version):
        raise ValueError("Invalid release version")
    if destination.exists():
        raise FileExistsError("Choose a fresh source stage directory")
    if destination == Path(destination.anchor) or destination == root or destination.is_relative_to(root):
        raise ValueError("The source stage must be a dedicated directory outside the source tree")
    for parent in destination.parents:
        if _is_link(parent):
            raise ValueError("Output directory link ancestors are forbidden")
    inputs = {path.relative_to(root).as_posix(): path for path in source_files(root)}
    required = ("cs2career/__init__.py", "tools/career3d_service.py", PROJECT + "/project.godot",
                PROJECT + "/data/career_link.json", PROJECT + "/data/ui_style.json", RTS_PROJECT + "/project.godot", "LICENSE")
    missing = [name for name in required if name not in inputs]
    if missing:
        raise ValueError("Missing required public source files: " + ", ".join(missing))
    own_assets, own_fonts = root / PROJECT / "assets", root / PROJECT / "fonts"
    asset_root = Path(asset_root) if asset_root is not None else own_assets if own_assets.is_dir() else DEFAULT_ASSET_ROOT
    font_root = Path(font_root) if font_root is not None else own_fonts if own_fonts.is_dir() else DEFAULT_FONT_ROOT
    resources = {}
    for name in MODEL_NAMES:
        relative, path = PROJECT + "/assets/" + name, asset_root / name
        _check_file(path, relative)
        _verify_glb(path, relative)
        resources[relative] = path
    for name, expected in FONT_HASHES.items():
        relative, path = PROJECT + "/fonts/" + name, font_root / name
        _check_file(path, relative)
        if file_hash(path) != expected:
            raise ValueError("Pinned font/license hash mismatch: " + name)
        resources[relative] = path
    # The character .blend is an original, small construction dependency, not a
    # previous saved career or a generated editor cache.
    if (asset_root / "chicken_source.blend").is_file():
        resources[PROJECT + "/assets/chicken_source.blend"] = asset_root / "chicken_source.blend"
    audio_root = asset_root / "audio"
    for name in sorted(AUDIO_NAMES):
        if (audio_root / name).is_file():
            resources[PROJECT + "/assets/audio/" + name] = audio_root / name
    external = dict(EXTERNAL_AUTHORING_SOURCES) if include_external_authoring else {}
    for relative, path in external.items():
        if path.is_file() and relative not in inputs:
            resources[relative] = path
    for relative, path in (extra_sources or {}).items():
        relative = _extra_target(relative)
        path = Path(path)
        if path.suffix.casefold() == ".dll" or path.suffix.casefold() != PurePosixPath(relative).suffix.casefold():
            raise ValueError("Additional source type cannot be renamed or disguise a DLL: " + relative)
        if relative in inputs or relative in resources:
            raise ValueError("Additional source collides with selected source: " + relative)
        resources[relative] = path
    inputs.update(resources)
    for relative, path in inputs.items():
        if excluded_path(relative):
            raise ValueError("Private/generated artifact selected: " + relative)
        _check_file(path, relative)
    if PROJECT + "/assets/audio/arena_entrance.ogg" in inputs and "licenses/GeneralUser-GS-LICENSE.txt" not in inputs:
        raise ValueError("Rendered entrance music requires its GeneralUser GS attribution/license")
    _io_path(destination.parent).mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".sources-", dir=_io_path(destination.parent)))
    manifest, transforms = {}, []
    try:
        for relative, source in sorted(inputs.items()):
            target = temporary / relative
            _io_path(target.parent).mkdir(parents=True, exist_ok=True)
            is_text = source.suffix.casefold() in TEXT_SUFFIXES or source.name in SPECIAL_TEXT_NAMES
            if is_text:
                text = _io_path(source).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
                if CREDENTIAL.search(text):
                    raise ValueError("Possible credential in public source: " + relative)
                text, home_count = _portable_home(text)
                if home_count:
                    transforms.append({"path": relative, "kind": "private-home-to-public-placeholder", "count": home_count})
                if relative == PROJECT + "/data/career_link.json":
                    config = json.loads(text)
                    config.update(python="python", repo_root="../..", data_dir="runtime/career")
                    text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
                    transforms.append({"path": relative, "kind": "portable-source-backend-config"})
                elif relative == PROJECT + "/data/media.json":
                    config = json.loads(text)
                    config["team_manifest"] = "../../../media/teams/team-media.json"
                    config["skin_cache_roots"] = ["../../../media/skin_art"]
                    for map_id, row in config.get("map_backgrounds", {}).items():
                        if isinstance(row, dict):
                            row["path"] = "../../../media/maps/" + map_id + ".png"
                    text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
                    transforms.append({"path": relative, "kind": "portable-optional-media-config"})
                elif relative == PROJECT + "/data/ui_style.json":
                    config = json.loads(text)
                    config.pop("development_cache", None)
                    text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
                    transforms.append({"path": relative, "kind": "remove-development-font-cache"})
                elif relative in (PROJECT + "/启动样板.cmd", RTS_PROJECT + "/启动2D单机.cmd"):
                    text = _launcher(relative)
                    transforms.append({"path": relative, "kind": "portable-godot-source-launcher"})
                elif relative == PROJECT + "/source/build_walkable_arena.py":
                    text, count = re.subn(r'bpy\.ops\.wm\.open_mainfile\(filepath=r"[^"\n]*grand_major_arena\.blend"\)',
                        "bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/grand_major_arena.blend'))", text)
                    if count:
                        transforms.append({"path": relative, "kind": "local-arena-authoring-input", "count": count})
                elif relative == PROJECT + "/assets/audio/arena_entrance_composition.json":
                    composition = json.loads(text)
                    if isinstance(composition.get("render"), dict):
                        for kind in ("ogg", "wav"):
                            if kind in composition["render"]:
                                composition["render"][kind] = "arena_entrance." + kind
                    text = json.dumps(composition, ensure_ascii=False, indent=2) + "\n"
                    transforms.append({"path": relative, "kind": "portable-music-provenance"})
                verify_public_text(text, relative)
                _io_path(target).write_text(text, encoding="utf-8", newline="\n")
            else:
                _verify_binary(source, relative)
                shutil.copyfile(_io_path(source), _io_path(target))
            manifest[relative] = file_hash(target)
        guide = temporary / "SOURCE_BUILD.md"
        guide.write_text(BUILD_GUIDE, encoding="utf-8", newline="\n")
        manifest[guide.name] = file_hash(guide)
        report = {
            "schema_version": 1, "version": version, "source_files": len(manifest),
            "files": manifest, "transforms": transforms, "verified_fonts": dict(FONT_HASHES),
            "models": {name: manifest[PROJECT + "/assets/" + name] for name in MODEL_NAMES},
            "omitted": sorted(PRIVATE_DIRS), "live_cs2_test": "pending",
        }
        stage_manifest = temporary / "SOURCE_STAGE_MANIFEST.json"
        stage_manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        # A racing producer must not cause a Windows rename to replace an output.
        if destination.exists():
            raise FileExistsError("Source stage appeared during validation")
        temporary.rename(_io_path(destination))
        return report
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
