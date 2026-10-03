"""Stage the reviewed offline CS2 runtime without reading player inventories.

The input is a verified compatibility capsule, never a live game directory.
The optional game directory is read only: it proves matching binaries and supplies
the reviewed InventorySimulator signatures. Installation belongs to the app's
explicit user-selected installation/launch workflow, not this packaging tool.
"""
from __future__ import annotations

import argparse
import base64
import configparser
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CAPSULE_MANIFEST = "0782be65c010c0b05d091b363d166a380e6c3d6b3e08256233e48314ab9fe7e9"
REVIEWED_INVENTORY_GAMEDATA = "0492cdc6b0e2e6b92406b2838f18c4a06a9e70359a2dc05bc0e6a209a6d478cb"
PLUGINS = frozenset(("BotAI", "BotAimImprover", "BotBuy", "BotControllerImpl",
    "BotHiderImpl", "BotRandomizer", "BotState", "CareerMatch", "NadeSystem",
    "RayTraceImpl", "RoundDamageRecap"))
SHARED = frozenset(("0Harmony", "BotControllerApi", "BotHiderApi", "RayTraceApi"))
NATIVES = frozenset(("BotController", "BotHider", "BotVision", "RayTrace"))
CFG_FILES = frozenset(("bot_buy.cfg", "my_bot_normal_config.cfg", "my_bot_ffa_config.cfg",
    "gamemode_armsrace.cfg", "gamemode_casual.cfg", "gamemode_competitive.cfg",
    "gamemode_competitive_offline.cfg", "gamemode_competitive2v2.cfg",
    "gamemode_competitive2v2_offline.cfg", "gamemode_custom.cfg", "gamemode_deathmatch.cfg",
    "gamemode_dm_freeforall.cfg", "gamemode_retakecasual.cfg", "gamemode_teamdeathmatch.cfg",
    "gamemode_workshop.cfg"))
FRAMEWORK_CONFIG = frozenset(("core.json", "core.example.json"))
RUNTIME_EXTENSIONS = frozenset((".dll", ".exe", ".json", ".xml", ".txt", ".dat", ".bin"))
PRIVATE_PARTS = frozenset(("save", "logs", "reports", "tests-output", "cache", "temp",
    "backup", "demos", "demo", "inventories", "captures", "plugins_off", "node_modules",
    "obj", "bin", ".git"))
PRIVATE_NAMES = frozenset(("bot_info.json", "inventories.json", "owner.txt", "cs2.json",
    "career.json", "match_request.json", "match_result.json", "tactical_playbook.json",
    "tactical_routes.json", "admins.json", "admin_groups.json", "admin_overrides.json",
    "admins.example.json", "admin_groups.example.json", "admin_overrides.example.json"))
STEAM_ID = re.compile(r"\b7656119\d{10}\b")
PRIVATE_TEXT = re.compile(r"(?i)(?:[a-z]:[/\\]users[/\\](?!public\b|default\b)[^/\\\s]+|"
    r"(?:ghp_|github_pat_)[a-z0-9_]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
SOURCE_SUFFIXES = frozenset((".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".inc",
    ".cs", ".csproj", ".sln", ".props", ".targets", ".cmake", ".py", ".ps1", ".sh",
    ".yml", ".yaml", ".md", ".txt", ".json", ".toml", ".xml", ".cfg", ".vdf", ".ini",
    ".proto", ".asm", ".s", ".def", ".in", ".ac", ".am", ".m4", ".patch", ".bat",
    ".cmd", ".lib", ".a", ".mak", ".lua", ".js", ".ts", ".css", ".html",
    ".projitems", ".shproj", ".resx", ".rc", ".rc2", ".vcxproj", ".vcxitems",
    ".filters", ".manifest", ".mk", ".map", ".snk"))
BINARY_SOURCE_SUFFIXES = frozenset((".a", ".lib", ".snk"))
# The release tags and source commits were checked against the actual reviewed
# PE versions and official GitHub release/source records on 2026-10-02.
SOURCE_PINS = (
    ("BotController", "XBribo/CS2-Bot-Controller", "451c7ba8ddb007eeb4d72edf291f6e0cbb051e56", "AGPL-3.0-only"),
    ("BotHider", "XBribo/CS2-Bot-Hider", "1c8fc7dea8111a598084f925b7653bb32378b988", "AGPL-3.0-only"),
    ("BotVision", "XBribo/CS2-Bot-Vision", "33ab01fc5ec4e27b6f07aff653d54638ad84ebcb", "AGPL-3.0-only"),
    ("CounterStrikeSharp", "roflmuffin/CounterStrikeSharp", "653d651f1ac09ac1ddb423d588f871b891038860", "GPL-3.0-with-plugin-MIT-exception"),
    # RayTrace carries this older managed API assembly beside its plugin.
    ("CounterStrikeSharp-API-1.0.371", "roflmuffin/CounterStrikeSharp", "3923c5d7b9aafe971884a3bd9287500da34bfa6d", "GPL-3.0-with-plugin-MIT-exception"),
    ("Metamod", "alliedmodders/metamod-source", "05c5c63a9d595cb84021c3a51fe38366ba4a12a5", "Zlib"),
    ("RayTrace", "FUNPLAY-pro-CS2/Ray-Trace", "b6c81b3b53839628ed58085b6f57237d7868ab55", "GPL-3.0"),
    ("BotAimImprover", "ed0ard/CS2-Bullseye-Bot", "91b7be8c8dbcf49ac5746f1c048742937a1f632d", "AGPL-3.0"),
    ("BotRandomizer", "ed0ard/CS2-Bot-Randomizer", "276f1ce6fd7f291be124d2023a2716ed720fb6d7", "AGPL-3.0"),
    ("BotImprover-managed", "ed0ard/CS2-Bot-Improver", "5aabff41be0f727f3e0ab59e03a94076c1338c3e", "AGPL-3.0-excluding-Panel"),
    ("Harmony", "pardeike/Harmony", "a264a1bf1ce689e4589e8dcc54b1e2818602a90a", "MIT"),
)
_DOWNLOAD_CACHE: Path | None = None
PINNED_SUBMODULES = {
    ("roflmuffin/CounterStrikeSharp", "653d651f1ac09ac1ddb423d588f871b891038860"): {
        "libraries/DynoHook": "d7f8ebb059dcfb20d5800051cf1c6e702f688470",
        "libraries/Protobufs": "9ce69f52d9159611cb075c5598e63290192ec5c0",
        "libraries/asmjit": "0dd16b0a98ae1da48563c9cc62f757a9e6bbe9b6",
        "libraries/dyncall": "3bcebd526fe16f0aa520e32597ff3dbfbf30b1e4",
        "libraries/funchook": "7cb8819594f0d586454011ab691fab4edb625068",
        "libraries/hl2sdk-cs2": "625bfd4e39816ad0e1eae3b3144a3b5425c5c7a0",
        "libraries/metamod-source": "fa6f80e4662e5b96cc2e97722d812f374581dfd8",
        "libraries/spdlog": "91807c2e718890ca2c0c88620326c6919ce041f4",
    },
    ("FUNPLAY-pro-CS2/Ray-Trace", "b6c81b3b53839628ed58085b6f57237d7868ab55"): {
        "vendor/khook": "f6785fd70869972841d9bc0a87013355eb9ce7e1",
        "vendor/spdlog": "0209b12c502bbdd37e04d238d74af851457e8210",
    },
}
NUGET_CACHES = (Path("D:/CS2CareerBuilds/v1.6.0/cache/nuget"),
    Path("D:/CS2CareerBuilds/local-actions-v2/nuget"), Path("D:/CS2BotLab/build/nuget"))
REQUIRED_FILES = tuple(sorted(
    [f"addons/{name}/bin/win64/{name}.dll" for name in NATIVES]
    + [f"addons/{name}/gamedata.json" for name in NATIVES]
    + [f"addons/counterstrikesharp/plugins/{name}/{name}.dll" for name in PLUGINS]
    + [f"addons/counterstrikesharp/shared/{name}/{name}.dll" for name in SHARED]
    + ["addons/metamod/bin/win64/server.dll", "addons/metamod/bin/win64/metamod.2.cs2.dll",
       "addons/metamod/counterstrikesharp.vdf", "addons/metamod/BotController.vdf",
       "addons/metamod/BotHider.vdf", "addons/metamod/BotVision.vdf", "addons/metamod/RayTrace.vdf",
       "addons/counterstrikesharp/bin/win64/counterstrikesharp.dll",
       "addons/counterstrikesharp/api/CounterStrikeSharp.API.dll",
       "addons/counterstrikesharp/api/CounterStrikeSharp.API.runtimeconfig.json",
       "addons/counterstrikesharp/dotnet/dotnet.exe", "addons/counterstrikesharp/dotnet/LICENSE.txt",
       "addons/counterstrikesharp/dotnet/ThirdPartyNotices.txt",
       "addons/counterstrikesharp/gamedata/gamedata.json", "addons/counterstrikesharp/configs/core.json",
       "addons/BotHider/config.json", "addons/BotHider/map_whitelist.json", "addons/BotVision/config.json"]
))


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or "\\" in value or path.is_absolute() or any(p in (".", "..") for p in path.parts) or ":" in value:
        raise ValueError("Unsafe relative package path")
    return path


def _checked_file(root: Path, relative: str) -> Path:
    parts = _relative(relative).parts
    path = root.joinpath(*parts)
    for index in range(1, len(parts) + 1):
        if root.joinpath(*parts[:index]).is_symlink():
            raise ValueError("Symlinks are not accepted in runtime inputs")
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"Missing runtime file: {relative}")
    return path


def runtime_allowed(relative: str) -> bool:
    """Folder+filename allowlist; eligibility does not bypass checksum proof."""
    path = _relative(relative)
    p = path.parts
    name = path.name.casefold()
    if name in PRIVATE_NAMES or path.suffix.casefold() in (".pdb", ".log", ".dem", ".pyc") or "previous" in name:
        return False
    if any(part.casefold() in ("logs", "reports", "cache", "temp", "backup", "plugins_off") for part in p):
        return False
    if len(p) == 2 and p[0] == "cfg":
        return p[1] in CFG_FILES
    if p[:2] == ("addons", "metamod"):
        return (len(p) == 3 and p[2] in ("BotController.vdf", "BotHider.vdf", "BotVision.vdf",
            "RayTrace.vdf", "counterstrikesharp.vdf", "metaplugins.ini")) or (
            p[:4] == ("addons", "metamod", "bin", "win64") and len(p) == 5 and p[4] in ("server.dll", "metamod.2.cs2.dll"))
    if len(p) == 2 and p[0] == "addons":
        return p[1] in ("metamod.vdf", "metamod_x64.vdf")
    if len(p) >= 3 and p[0] == "addons" and p[1] in NATIVES:
        return (len(p) == 5 and p[2:4] == ("bin", "win64") and p[4] == p[1] + ".dll") or (
            len(p) == 3 and (p[2] == "gamedata.json" or
            (p[1] == "BotHider" and p[2] in ("config.json", "map_whitelist.json")) or
            (p[1] == "BotVision" and p[2] == "config.json")))
    if p[:2] != ("addons", "counterstrikesharp") or len(p) < 4:
        return False
    if p[2] in ("api", "dotnet"):
        return path.suffix.casefold() in RUNTIME_EXTENSIONS
    if p[2] == "bin":
        return len(p) == 5 and p[3] == "win64" and path.suffix.casefold() == ".dll"
    if p[2] == "configs":
        return len(p) == 4 and p[3] in FRAMEWORK_CONFIG
    if p[2] == "gamedata":
        return len(p) == 4 and p[3] == "gamedata.json"
    if p[2] == "lang":
        return len(p) == 4 and path.suffix == ".json"
    if p[2] in ("plugins", "shared") and p[3] in (PLUGINS if p[2] == "plugins" else SHARED):
        if path.suffix == ".dll":
            return len(p) == 5 or (len(p) >= 7 and p[4] == "runtimes")
        if len(p) == 5 and p[4] == p[3] + ".deps.json":
            return True
        if p[3] == "BotRandomizer" and len(p) == 5:
            return p[4] in ("cosmetic_catalog.json", "charm_placements.json")
        if p[3] == "NadeSystem" and len(p) == 6 and p[4] == "grenades":
            return re.fullmatch(r"(?:de|cs)_[a-z0-9_]+_(?:flash|he|molotov|smoke)\.json", p[5]) is not None
    return False


def _public_text(blob: bytes, label: str, *, allow_id_base: bool = False) -> None:
    text = blob.decode("utf-8-sig", errors="replace")
    if PRIVATE_TEXT.search(text):
        raise ValueError(f"Private path or credential in {label}")
    if allow_id_base:
        text = text.replace("76561197960265728", "STEAM_ID_BASE")
    if STEAM_ID.search(text):
        raise ValueError(f"Account identifier in {label}")


def _runtime_plan(mod_source: Path) -> dict[str, tuple[Path, str]]:
    manifest_path = _checked_file(mod_source.parent, "capsule-files.json")
    if digest(manifest_path) != EXPECTED_CAPSULE_MANIFEST:
        raise ValueError("Runtime capsule manifest has not been reviewed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict):
        raise ValueError("Invalid runtime manifest")
    planned = {}
    for relative, expected in manifest.items():
        if not runtime_allowed(relative):
            continue
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError("Invalid runtime checksum")
        source = _checked_file(mod_source, relative)
        if digest(source) != expected:
            raise ValueError(f"Runtime checksum differs from reviewed capsule: {relative}")
        if source.suffix.casefold() in (".json", ".cfg", ".vdf", ".ini", ".txt", ".xml"):
            _public_text(source.read_bytes(), relative)
        planned[relative] = (source, expected)
    for path in mod_source.rglob("*"):
        if path.is_file() and runtime_allowed(path.relative_to(mod_source).as_posix()):
            if path.relative_to(mod_source).as_posix() not in planned:
                raise ValueError("Unreviewed file in an allowed runtime folder")
    missing = sorted(set(REQUIRED_FILES) - planned.keys())
    if missing:
        raise ValueError("Incomplete runtime: " + ", ".join(missing))
    # Always use the application's matching managed source/binaries. Never copy
    # match requests, results, route archives or natural-motion experiments.
    for name in ("CareerMatch", "BotBuy"):
        for filename in (name + ".dll", name + ".deps.json"):
            source = _checked_file(ROOT, f"vendor/{name}/{filename}")
            planned[f"addons/counterstrikesharp/plugins/{name}/{filename}"] = (source, digest(source))
    return planned


def _source_allowed(relative: str, *, improver: bool = False) -> bool:
    path = _relative(relative)
    parts = {p.casefold() for p in path.parts}
    if parts & PRIVATE_PARTS or "panel" in parts or path.name.casefold() in PRIVATE_NAMES:
        return False
    if any(p in ("tests", "test", "examples", "example", "testplugin", "nativetestsplugin") or p.endswith((".tests", ".tests.native")) for p in parts):
        return False
    if any("previous" in p.casefold() for p in path.parts):
        return False
    # Published/generated API documentation is not a build input. Harmony's
    # documentation manifest embeds its author's build-machine paths; retain
    # the actual source and notices, not that generated site output.
    if path.parts[0].casefold() == "docs":
        return False
    if improver:
        # Upstream's named-player BotProfile DB and BotHider IDs are data, not
        # build inputs for the managed plugins. Its Panel has a separate license.
        if path.parts[0] in ("overrides", "Panel", "docs", "cfg"):
            return False
        if path.parts[0] == "addons" and not relative.startswith("addons/counterstrikesharp/"):
            return False
    return (path.suffix.casefold() in SOURCE_SUFFIXES or path.name.startswith(("LICENSE", "COPYING", "NOTICE"))
        or path.name in ("Makefile", "CMakeLists.txt", "configure", "Dockerfile", ".gitmodules", ".gitignore", "AMBuildScript", "AMBuilder", "_._"))


def _download(url: str) -> bytes:
    if not url.startswith(("https://api.github.com/", "https://codeload.github.com/", "https://api.nuget.org/v3-flatcontainer/")):
        raise ValueError("Source/notice download must use official GitHub or NuGet endpoints")
    cache_path = checksum_path = None
    if _DOWNLOAD_CACHE is not None:
        _DOWNLOAD_CACHE.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        cache_path, checksum_path = _DOWNLOAD_CACHE / (key + ".download"), _DOWNLOAD_CACHE / (key + ".sha256")
        if cache_path.is_file() and checksum_path.is_file() and digest(cache_path) == checksum_path.read_text("ascii").strip():
            return cache_path.read_bytes()
    request = urllib.request.Request(url, headers={"User-Agent": "CS2Career-reviewed-source-package"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                blob = response.read()
            if cache_path is not None and checksum_path is not None:
                cache_path.write_bytes(blob)
                checksum_path.write_text(hashlib.sha256(blob).hexdigest(), encoding="ascii")
            return blob
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 3:
                raise
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError("Source download failed")


def _fetch_source(repo: str, commit: str, output: zipfile.ZipFile, legal: Path,
                  prefix: str = "", visited: set[tuple[str, str]] | None = None,
                  *, improver: bool = False, managed_api_only: bool = False) -> list[dict]:
    """Include exact source and recursively pinned Git submodules in one ZIP."""
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid immutable source pin")
    visited = set(visited or ())
    if (repo, commit) in visited:
        return []
    visited.add((repo, commit))
    url = f"https://codeload.github.com/{repo}/zip/{commit}"
    archive_blob = _download(url)
    archive_hash = hashlib.sha256(archive_blob).hexdigest()
    modules = ""
    included = 0
    skipped = 0
    sanitized_docs = []
    with zipfile.ZipFile(io.BytesIO(archive_blob)) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Source archive contains a symlink")
            full = _relative(entry.filename)
            if len(full.parts) < 2:
                continue
            relative = PurePosixPath(*full.parts[1:]).as_posix()
            if managed_api_only and "/" in relative and not relative.startswith("managed/CounterStrikeSharp.API/"):
                skipped += 1
                continue
            if relative == ".gitmodules":
                modules = archive.read(entry).decode("utf-8-sig")
            if not _source_allowed(relative, improver=improver):
                skipped += 1
                continue
            blob = archive.read(entry)
            if PurePosixPath(relative).suffix.casefold() == ".md":
                # Installation examples may contain the author's sample SteamID.
                # Preserve code verbatim; anonymize documentation examples only.
                text = blob.decode("utf-8-sig")
                cleaned = STEAM_ID.sub("<STEAM_ID>", text)
                cleaned = PRIVATE_TEXT.sub("<PRIVATE_EXAMPLE_REMOVED>", cleaned)
                if cleaned != text:
                    blob = cleaned.encode("utf-8")
                    sanitized_docs.append(relative)
            elif PurePosixPath(relative).suffix.casefold() in (".cs", ".c", ".cpp", ".h", ".hpp"):
                # API documentation also appears in source comments. Change only
                # unambiguous comments; any account literal in executable code
                # still fails the scan below.
                text = blob.decode("utf-8-sig")
                lines = []
                for line in text.splitlines(keepends=True):
                    index = line.find("//")
                    if re.match(r"^\s*//", line):
                        line = STEAM_ID.sub("<STEAM_ID>", line)
                        line = PRIVATE_TEXT.sub("<PRIVATE_EXAMPLE_REMOVED>", line)
                    elif index >= 0 and not any(quote in line[:index] for quote in ('"', "'")):
                        line = line[:index] + STEAM_ID.sub("<STEAM_ID>", PRIVATE_TEXT.sub("<PRIVATE_EXAMPLE_REMOVED>", line[index:]))
                    lines.append(line)
                cleaned = "".join(lines)
                if cleaned != text:
                    blob = cleaned.encode("utf-8")
                    sanitized_docs.append(relative)
            if PurePosixPath(relative).suffix.casefold() not in BINARY_SOURCE_SUFFIXES:
                _public_text(blob, f"{repo}/{relative}", allow_id_base=True)
            output.writestr(prefix + relative, blob)
            included += 1
            if "/" not in relative and relative.startswith(("LICENSE", "COPYING", "NOTICE")):
                notice = legal / (re.sub(r"[^a-zA-Z0-9_.-]", "_", repo) + "-" + relative)
                if not notice.exists():
                    notice.write_bytes(blob)
    records = [{"repository": repo, "commit": commit, "archive_url": url,
                "download_sha256": archive_hash, "source_prefix": prefix,
                "source_files": included, "excluded_data_files": skipped,
                "anonymized_documentation_examples": sanitized_docs,
                "scope": "managed API production project and root build/notices" if managed_api_only else "production source including pinned submodules"}]
    if modules and not managed_api_only:
        links = _submodule_links(repo, commit)
        config = configparser.ConfigParser()
        config.read_string(modules)
        for section in config.sections():
            path, module_url = config[section]["path"], config[section]["url"]
            if path not in links:
                continue
            match = re.fullmatch(r"https://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?", module_url)
            if not match:
                raise ValueError("Unrecognized source submodule origin")
            records.extend(_fetch_source(match[1], links[path], output, legal,
                prefix + _relative(path).as_posix() + "/", visited))
    return records


def _submodule_links(repo: str, commit: str) -> dict[str, str]:
    if (repo, commit) in PINNED_SUBMODULES:
        return PINNED_SUBMODULES[(repo, commit)]
    if _DOWNLOAD_CACHE is None:
        tree = json.loads(_download(f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1"))
        return {row["path"]: row["sha"] for row in tree["tree"] if row.get("mode") == "160000"}
    # Public Git fetch does not use the REST API quota. Fetch one immutable
    # commit into our isolated download cache and inspect its tree without a
    # checkout, credentials, or any write to the upstream repository.
    folder = _DOWNLOAD_CACHE / ("git-tree-" + hashlib.sha256(repo.encode()).hexdigest())
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    if not folder.exists():
        subprocess.run(["git", "init", "--bare", str(folder)], check=True, capture_output=True, env=env)
    existing = subprocess.run(["git", "-C", str(folder), "cat-file", "-e", commit], capture_output=True, env=env)
    if existing.returncode:
        for attempt in range(3):
            result = subprocess.run(["git", "-c", "http.version=HTTP/1.1", "-C", str(folder),
                "fetch", "--depth=1", "--filter=blob:none", "https://github.com/" + repo + ".git", commit],
                capture_output=True, env=env, timeout=120)
            if not result.returncode:
                break
        else:
            raise RuntimeError(f"Pinned source tree fetch failed: {repo}@{commit}")
    result = subprocess.run(["git", "-C", str(folder), "ls-tree", "-r", commit],
        check=True, capture_output=True, text=True, env=env)
    links = {}
    for line in result.stdout.splitlines():
        metadata, path = line.split("\t", 1)
        mode, kind, sha = metadata.split(" ", 2)
        if mode == "160000" and kind == "commit":
            links[path] = sha
    return links


def _stage_sources(target: Path) -> list[dict]:
    legal, third_party = target / "legal", target / "third_party"
    legal.mkdir(exist_ok=True)
    third_party.mkdir(exist_ok=True)
    records = []
    for name, repo, commit, license_name in SOURCE_PINS:
        archive_path = third_party / f"{name}-{commit[:12]}-source.zip"
        with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED) as output:
            trees = _fetch_source(repo, commit, output, legal, improver=name == "BotImprover-managed",
                managed_api_only=name == "CounterStrikeSharp-API-1.0.371")
        with zipfile.ZipFile(archive_path) as check:
            if check.testzip() is not None:
                raise ValueError("Corrupt corresponding-source ZIP")
        records.append({"component": name, "license": license_name,
            "source_archive": archive_path.relative_to(target).as_posix(),
            "source_archive_sha256": digest(archive_path), "source_trees": trees})
    own = third_party / "Career-managed-plugins-source.zip"
    with zipfile.ZipFile(own, "x", zipfile.ZIP_DEFLATED) as output:
        for name in ("CareerMatch", "BotBuy", "InventorySimulator", "InvsimCareer"):
            for path in sorted((ROOT / "vendor" / name).rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(ROOT).as_posix()
                if _source_allowed(relative):
                    source = target / relative if relative == "vendor/InventorySimulator/gamedata/inventory-simulator.json" else path
                    _public_text(source.read_bytes(), "application plugin source", allow_id_base=True)
                    output.write(source, relative)
        # CareerMatch embeds the tactical map metadata during compilation.
        output.write(ROOT / "cs2career/data/tactical_maps.json", "cs2career/data/tactical_maps.json")
        for relative in ("LICENSE", "RECOVERED_SOURCE.md", "THIRD_PARTY_NOTICES.md", "licenses/InventorySimulator-MIT.txt", "licenses/CS2Career-MIT-legacy.txt"):
            blob = _checked_file(ROOT, relative).read_bytes()
            _public_text(blob, relative, allow_id_base=True)
            output.writestr(relative, blob)
    records.append({"component": "CareerMatch/BotBuy/InventorySimulator/InvsimCareer",
        "source_archive": own.relative_to(target).as_posix(), "source_archive_sha256": digest(own),
        "license": "AGPL-3.0-only/MIT", "inventory_source_status": "Recovered source; compile checked, recompiled live equivalence unverified"})
    for relative in ("LICENSE", "RECOVERED_SOURCE.md", "THIRD_PARTY_NOTICES.md", "licenses/InventorySimulator-MIT.txt", "licenses/CS2Career-MIT-legacy.txt"):
        shutil.copy2(_checked_file(ROOT, relative), legal / Path(relative).name)
    (legal / "BOT_RUNTIME_NOTICES.txt").write_text(
        "Reviewed offline Windows x64 CS2 runtime, packaged 2026-10-02.\n"
        "BotController 0.7.0 / BotHider 0.5.0 / BotVision 0.3.0: AGPL-3.0-only.\n"
        "CounterStrikeSharp 1.0.376: GPL-3.0; its plugin MIT exception is preserved.\n"
        "RayTrace's adjacent CounterStrikeSharp managed API 1.0.371 has its exact API source too.\n"
        "Metamod 2.0.0-dev+1472: zlib/libpng. RayTrace: GPL-3.0.\n"
        "Bot Improver managed source is AGPL-3.0. Its PolyForm Strict Panel is excluded.\n"
        "Nested dependencies retain their original licenses in the corresponding source ZIPs.\n"
        "Licensing caveat: the pinned alliedmodders HL2SDK cs2 mirror has Valve copyright headers\n"
        "but no root SDK license at that pin; unrestricted/commercial SDK redistribution is not certified.\n"
        "Sample admin data, tests/examples with account fixtures and named-player roster data are\n"
        "excluded from source ZIPs; build the production plugin/API projects rather than test solutions.\n"
        "Public upstream strong-name keys and build resources are retained only in pinned source archives.\n"
        "The .NET runtime retains its LICENSE.txt and ThirdPartyNotices.txt.\n"
        "Steam, CS2, player identities, inventories, owner files, demos and game logs are excluded.\n"
        "InventorySimulator/InvsimCareer binaries match the historical local versions. Their recovered\n"
        "source has compile validation only; recompiled live equivalence remains unverified.\n"
        "Legacy BotAI/BotState/NadeSystem/RoundDamageRecap source is preserved from the clean\n"
        "Bot Improver source pin; deterministic recompile equivalence has not been established.\n"
        "No game's files are changed by this packaging tool.\n", encoding="utf-8")
    return records


def _nuget_notice(package: str, version: str, destination: Path) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", package) or not re.fullmatch(r"[A-Za-z0-9_.+-]+", version):
        raise ValueError("Invalid NuGet package pin")
    key = package.lower()
    url = f"https://api.nuget.org/v3-flatcontainer/{key}/{version.lower()}/{key}.{version.lower()}.nupkg"
    blob = None
    for cache in NUGET_CACHES:
        folder = cache / key / version.lower()
        candidate = folder / f"{key}.{version.lower()}.nupkg"
        checksum = folder / f"{key}.{version.lower()}.nupkg.sha512"
        if candidate.is_file() and checksum.is_file():
            cached = candidate.read_bytes()
            if hashlib.sha512(cached).digest() == base64.b64decode(checksum.read_text("ascii").strip()):
                blob = cached
                break
    if blob is None:
        blob = _download(url)
    folder = destination / f"{package}-{version}"
    folder.mkdir()
    license_files = []
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        nuspec_name = next(name for name in archive.namelist() if name.endswith(".nuspec"))
        metadata = ET.fromstring(archive.read(nuspec_name))
        values = {}
        for node in metadata.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag in ("authors", "copyright", "license", "licenseUrl", "repository"):
                values[tag] = {"text": node.text or "", "attributes": dict(node.attrib)}
        # Preserve the package's original attribution and licensing declaration.
        nuspec = archive.read(nuspec_name)
        _public_text(nuspec, "NuGet package attribution")
        (folder / "PACKAGE_METADATA.nuspec").write_bytes(nuspec)
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            path = _relative(entry.filename)
            if path.suffix.casefold() not in (".txt", ".md", ""):
                continue
            if re.search(r"(?i)(license|copying|notice)", path.name):
                notice = archive.read(entry)
                _public_text(notice, "NuGet license")
                filename = str(len(license_files) + 1) + "-" + path.name
                (folder / filename).write_bytes(notice)
                license_files.append(filename)
    expression = values.get("license", {}).get("text", "")
    if not license_files:
        # Older NuGet packages use an SPDX expression or license URL without
        # embedding a text file. Keep their original nuspec with its authors and
        # copyright and add the declared, unmodified standard license text.
        if expression == "MIT" or "mit" in values.get("licenseUrl", {}).get("text", "").lower():
            canonical = ROOT / "licenses/runtime/orjson/MIT.txt"
        elif expression == "Apache-2.0" or "apache" in values.get("licenseUrl", {}).get("text", "").lower():
            canonical = ROOT / "licenses/runtime/orjson/Apache-2.0.txt"
        elif expression in ("GPL-3.0-only", "GPL-3.0-or-later"):
            canonical = destination.parent / "roflmuffin_CounterStrikeSharp-LICENSE.GPL3"
        elif expression == "BSD-2-Clause":
            repository = values.get("repository", {}).get("attributes", {})
            repo_url, commit = repository.get("url", ""), repository.get("commit", "")
            match = re.fullmatch(r"https://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?", repo_url)
            if not match or not re.fullmatch(r"[a-f0-9]{40}", commit):
                raise ValueError("BSD notice requires the package's immutable upstream repository pin")
            source_url = f"https://codeload.github.com/{match[1]}/zip/{commit}"
            source_blob = _download(source_url)
            with zipfile.ZipFile(io.BytesIO(source_blob)) as upstream:
                name = next(name for name in upstream.namelist()
                    if len(_relative(name).parts) == 2 and PurePosixPath(name).name.casefold().startswith("license"))
                notice = upstream.read(name)
                _public_text(notice, "pinned upstream BSD license")
                (folder / "DECLARED_LICENSE.txt").write_bytes(notice)
            values["license_source"] = {"text": source_url,
                "attributes": {"download_sha256": hashlib.sha256(source_blob).hexdigest()}}
            canonical = None
        else:
            raise ValueError(f"Missing license text for pinned NuGet package {package}/{version}")
        # These files reproduce standard permissive license terms. Package
        # authors/copyright remain in PACKAGE_METADATA.nuspec alongside them.
        if canonical is not None:
            shutil.copy2(canonical, folder / "DECLARED_LICENSE.txt")
        license_files.append("DECLARED_LICENSE.txt")
    return {"package": package, "version": version, "nuget_url": url,
        "package_sha256": hashlib.sha256(blob).hexdigest(), "attribution": values,
        "notice_directory": "legal/nuget/" + folder.name, "license_files": license_files}


def _stage_dependency_notices(target: Path) -> list[dict]:
    libraries = set()
    for path in (target / "CS2BotImprover").rglob("*.deps.json"):
        metadata = json.loads(path.read_text(encoding="utf-8-sig"))
        for name, row in metadata.get("libraries", {}).items():
            if row.get("type") == "package":
                package, version = name.rsplit("/", 1)
                libraries.add((package, version))
    destination = target / "legal/nuget"
    destination.mkdir()
    with ThreadPoolExecutor(max_workers=6) as workers:
        futures = [workers.submit(_nuget_notice, package, version, destination) for package, version in sorted(libraries)]
        records = [future.result() for future in futures]
    (target / "legal/NUGET_NOTICES.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    return records


def stage_bot_runtime(mod_source: Path, target: Path, game_dir: Path | None = None) -> dict:
    """Create a fresh package staging directory; never install to a game.

    Layout: CS2BotImprover/ is the installable tree; legal/ and third_party/ are
    sibling package contents. vendor/ contains only the reviewed skin gamedata.
    Existing targets are rejected to avoid accidentally repackaging player data.
    """
    mod_source, target = Path(mod_source).resolve(), Path(target).resolve()
    if target.exists():
        raise FileExistsError("Choose a fresh bot-runtime staging directory")
    if target == mod_source or target.is_relative_to(mod_source) or mod_source.is_relative_to(target):
        raise ValueError("Runtime source and staging target must be separate")
    game = Path(game_dir).resolve() if game_dir is not None else None
    if game is not None and (target == game or target.is_relative_to(game) or game.is_relative_to(target)):
        raise ValueError("Package output must not overlap a game directory")
    plan = _runtime_plan(mod_source)
    proof = {}
    if game is not None:
        # Compare code/signatures only. Do not enumerate configs, inventories,
        # saves, account files or log contents from the live installation.
        for relative, (source, expected) in plan.items():
            if source.suffix == ".dll" or relative.endswith("/gamedata.json"):
                installed = _checked_file(game, relative)
                if digest(installed) != expected:
                    raise ValueError(f"Installed runtime differs from package input: {relative}")
                proof[relative] = expected
        skin_source = _checked_file(game, "addons/counterstrikesharp/gamedata/inventory-simulator.json")
    else:
        skin_source = _checked_file(ROOT, "vendor/InventorySimulator/gamedata/inventory-simulator.json")
    if digest(skin_source) != REVIEWED_INVENTORY_GAMEDATA:
        raise ValueError("Supply the read-only game_dir with the reviewed updated skin gamedata")
    _public_text(skin_source.read_bytes(), "inventory gamedata")
    presets = {}
    for difficulty in ("Low", "Medium", "High"):
        source = _checked_file(ROOT, f"cs2career/data/botprofile_presets/{difficulty}.db")
        blob = source.read_bytes()
        _public_text(blob, "anonymous difficulty template")
        if b"Template " not in blob or b"Default" not in blob or b"no upstream player list" not in blob:
            raise ValueError("Difficulty preset must be the anonymous application template")
        presets[f"overrides/{difficulty}/botprofile.db"] = (source, digest(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    # Errors retain their isolated partial stage for diagnosis, never erase it.
    pending = Path(tempfile.mkdtemp(prefix=".bot-runtime-pending-", dir=target.parent))
    runtime = pending / "CS2BotImprover"
    files = {}
    for relative, (source, expected) in sorted({**plan, **presets}.items()):
        destination = runtime.joinpath(*_relative(relative).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if digest(destination) != expected:
            raise OSError("Runtime copy checksum mismatch")
        files["CS2BotImprover/" + relative] = expected
    skin_relative = "vendor/InventorySimulator/gamedata/inventory-simulator.json"
    skin_target = pending / skin_relative
    skin_target.parent.mkdir(parents=True)
    shutil.copy2(skin_source, skin_target)
    files[skin_relative] = digest(skin_target)
    global _DOWNLOAD_CACHE
    previous_cache = _DOWNLOAD_CACHE
    _DOWNLOAD_CACHE = target.parent / ".bot-source-downloads"
    try:
        sources = _stage_sources(pending)
        dependencies = _stage_dependency_notices(pending)
    finally:
        _DOWNLOAD_CACHE = previous_cache
    manifest = {"schema": 1, "platform": "windows-x64", "runtime_files": files,
        "runtime_capsule_manifest_sha256": EXPECTED_CAPSULE_MANIFEST,
        "installed_code_and_signature_proof": proof,
        "source_packages": sources,
        "dependency_notices": dependencies,
        "licensing_caveats": ["Pinned HL2SDK cs2 mirror has Valve copyright headers but no root SDK license; unrestricted/commercial redistribution is not certified"],
        "skin_gamedata_sha256": REVIEWED_INVENTORY_GAMEDATA,
        "installable_directory": "CS2BotImprover",
        "excluded": ["player saves", "private settings", "owner/account IDs", "inventories",
            "named-player BotProfiles", "BotHider identity database", "reports", "logs", "demos",
            "caches", "Panel", "gameinfo templates", "BotLab and natural-route experiments"],
        "installation": "Only the app's explicit user-selected install/launch workflow copies the installable directory to CS2; Steam and CS2 must be provided by the tester."}
    (pending / "legal" / "BOT_RUNTIME_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    pending.rename(target)
    return {"runtime_dir": str(target / "CS2BotImprover"), "legal_dir": str(target / "legal"),
        "source_dir": str(target / "third_party"), "vendor_dir": str(target / "vendor"),
        "runtime_files": len(files), "source_packages": len(sources),
        "dependency_notices": len(dependencies),
        "live_files_read": len(proof) + (1 if game is not None else 0), "game_files_written": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--game-dir", type=Path, help="Read-only binary/signature comparison source")
    args = parser.parse_args()
    print(json.dumps(stage_bot_runtime(args.mod_source, args.target, args.game_dir), indent=2))
