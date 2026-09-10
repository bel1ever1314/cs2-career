# coding=utf-8
"""Hand a career match over to CS2 with named bots, then read the result back.

Needs the CS2 Bot Improver mod folder (CounterStrikeSharp + BotHider).
CareerMatch is bundled under vendor/ and copied in when the mod is installed.
Paths live in the save folder so a packaged build can be pointed at any install.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from ..paths import frozen, logo_dir, save_file, save_root, static_dir, vendor_root
from .profiles import active_manifest, generate_match_vpk, stable_player_id
from .result import pick_better_result, result_quality

SETTINGS_PATH = save_file("cs2.json")

SKINS_GAMEDATA_URLS = (
    "https://raw.githubusercontent.com/ianlucas/cs2-css-inventory-simulator/main/gamedata/inventory-simulator.json",
    "https://raw.githubusercontent.com/ianlucas/cs2-inventory-simulator-plugin/main/gamedata/inventory-simulator.json",
)

DEFAULTS = {
    "steam_exe": "",
    "csgo_path": "",
    "mod_source_path": "",
    # Difficulty is a generation preset in 1.5, not a persistent player DB.
    "difficulty": "Medium",
    "bot_aim": "mixed",
    "bot_nades": "normal",
    # "player" drops the BOT tag: managed bots publish a name, SteamID and ping.
    "bot_identity": "player",
    "skins_source_path": "",
}

DIFFICULTIES = ("Low", "Medium", "High")
AIM_MODES = ("head", "mixed", "body")
NADE_MODES = ("off", "less", "normal", "more", "max")
IDENTITY_MODES = ("player", "bot")

LIVE_MEMORY_BYTES = 80 * 1024 * 1024

# Long enough to pick a side and see the roster before the first real round.
WARMUP_SECONDS = 30

CS2_TAIL = Path("steamapps/common/Counter-Strike Global Offensive/game/csgo")


# ------------------------------------------------------------------ discovery


def _steam_roots() -> list[Path]:
    """Steam install dirs: registry first, then the usual drive spots."""
    found: list[Path] = []
    try:
        import winreg

        for hive, key, name in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    raw = winreg.QueryValueEx(handle, name)[0]
            except OSError:
                continue
            if raw:
                found.append(Path(str(raw).replace("/", "\\")))
    except ImportError:
        pass
    for drive in "CDEFGH":
        for tail in (r"Program Files (x86)\Steam", "Steam", "steam"):
            found.append(Path(f"{drive}:\\") / tail)
    seen: list[Path] = []
    for path in found:
        if path.is_dir() and path not in seen:
            seen.append(path)
    return seen


def _steam_libraries(root: Path) -> list[Path]:
    """Every library folder Steam knows about, the main one first."""
    libs = [root]
    vdf = root / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        try:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        for raw in re.findall(r'"path"\s*"([^"]+)"', text):
            lib = Path(raw.replace("\\\\", "\\"))
            if lib.is_dir() and lib not in libs:
                libs.append(lib)
    return libs


_FOUND: dict[str, str] = {}


def _cached(key: str, hunt) -> str:
    """Scanning the registry and libraries is only worth doing once."""
    if key not in _FOUND:
        _FOUND[key] = hunt()
    return _FOUND[key]


def find_steam_exe() -> str:
    def hunt() -> str:
        for root in _steam_roots():
            exe = root / "steam.exe"
            if exe.is_file():
                return str(exe)
        return ""

    return _cached("steam", hunt)


def find_csgo_path() -> str:
    def hunt() -> str:
        for root in _steam_roots():
            for lib in _steam_libraries(root):
                csgo = lib / CS2_TAIL
                if csgo.is_dir():
                    return str(csgo)
        return ""

    return _cached("csgo", hunt)


def resolve_csgo_path(raw: str | Path) -> Path:
    """Accept the Steam game root, game, or game\\csgo and land on game\\csgo."""
    text = str(raw or "").strip().strip('"')
    if not text or text in (".", "./"):
        return Path()
    path = Path(text)
    guesses = [path]
    if (path / "game" / "csgo").is_dir():
        guesses.append(path / "game" / "csgo")
    if path.name.lower() == "game" and (path / "csgo").is_dir():
        guesses.append(path / "csgo")
    for cand in guesses:
        norm = str(cand).replace("/", "\\").lower()
        if "\\game\\csgo" in norm and cand.is_dir():
            return cand
    return path


def is_csgo_dir(path: Path) -> bool:
    text = str(path).replace("/", "\\").lower()
    return bool(text) and text not in (".",) and path.is_dir() and "\\game\\csgo" in text


def _improver_here(path: Path) -> bool:
    """A Bot Improver folder has CSS plus the difficulty VPKs. CareerMatch is ours."""
    return (
        path.is_dir()
        and (path / "addons" / "metamod").is_dir()
        and (path / "addons" / "counterstrikesharp").is_dir()
        and (path / "overrides").is_dir()
    )


def _mod_here(path: Path) -> bool:
    return _improver_here(path)


def career_match_src(mod_source: Path | None = None) -> Path:
    """Prefer the copy shipped with this app; fall back to a CS2B tree."""
    bundled = vendor_root() / "CareerMatch"
    if (bundled / "CareerMatch.dll").is_file():
        return bundled
    if mod_source is not None:
        return Path(mod_source) / "addons" / "counterstrikesharp" / "plugins" / "CareerMatch"
    return bundled


def css_installed(csgo: Path) -> bool:
    return (csgo / "addons" / "metamod").is_dir() and (csgo / "addons" / "counterstrikesharp").is_dir()


def find_mod_source() -> str:
    """Look for the mod folder shipped next to the exe, then one level up."""

    def hunt() -> str:
        starts = [Path.cwd()]
        if frozen():
            starts.insert(0, Path(sys.executable).resolve().parent)
        bases: list[Path] = []
        for start in starts:
            for base in [start, *list(start.parents)[:2]]:
                if base not in bases:
                    bases.append(base)
        for base in bases:
            if _mod_here(base):
                return str(base)
            for child in ("CS2B", "CS2BotImprover", "CS2-Bot-Improver", "mod"):
                if _mod_here(base / child):
                    return str(base / child)
        return ""

    return _cached("mod", hunt)


def _autofill(cfg: dict) -> dict:
    """Replace paths that do not exist on this machine with detected ones."""
    if not Path(cfg["steam_exe"]).is_file():
        cfg["steam_exe"] = find_steam_exe() or cfg["steam_exe"]
    resolved = resolve_csgo_path(cfg.get("csgo_path") or "")
    if is_csgo_dir(resolved):
        cfg["csgo_path"] = str(resolved)
    else:
        cfg["csgo_path"] = find_csgo_path() or ""
    if not Path(cfg["mod_source_path"]).is_dir():
        cfg["mod_source_path"] = find_mod_source() or cfg["mod_source_path"]
    return cfg


def _clean(cfg: dict) -> dict:
    if cfg.get("difficulty") not in DIFFICULTIES:
        cfg["difficulty"] = DEFAULTS["difficulty"]
    if cfg.get("bot_aim") not in AIM_MODES:
        cfg["bot_aim"] = DEFAULTS["bot_aim"]
    if cfg.get("bot_nades") not in NADE_MODES:
        cfg["bot_nades"] = DEFAULTS["bot_nades"]
    if cfg.get("bot_identity") not in IDENTITY_MODES:
        cfg["bot_identity"] = DEFAULTS["bot_identity"]
    return cfg


def settings() -> dict:
    cfg = dict(DEFAULTS)
    if SETTINGS_PATH.exists():
        try:
            saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(saved, dict):
                cfg.update({k: v for k, v in saved.items() if v})
        except ValueError:
            pass
    _autofill(_clean(cfg))
    SETTINGS_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


def save_settings(patch: dict) -> dict:
    cfg = settings()
    old_difficulty = cfg.get("difficulty")
    if cs2_is_live() and patch.get("difficulty") and patch.get("difficulty") != cfg.get("difficulty"):
        raise ValueError("CS2 运行时不能修改难度。请完全退出游戏后再选择。")
    for key, val in patch.items():
        if key not in DEFAULTS or not val:
            continue
        if key == "csgo_path":
            cfg[key] = str(resolve_csgo_path(val))
        else:
            cfg[key] = val
    _clean(cfg)
    SETTINGS_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    # A staged match is a generated artifact of the chosen difficulty. Rebuild
    # it immediately while CS2 is closed so UI selection and active VPK agree.
    if old_difficulty != cfg.get("difficulty"):
        csgo = resolve_csgo_path(cfg.get("csgo_path") or "")
        request_path = plugin_dir(csgo) / "match_request.json"
        if is_csgo_dir(csgo) and request_path.is_file():
            try:
                match = json.loads(request_path.read_text(encoding="utf-8-sig"))
                if match.get("active") and int(match.get("schema_version") or 0) == 2:
                    install_match_avatars(csgo, match)
                    generate_match_vpk(csgo, match, cfg["difficulty"])
                    temp = request_path.with_suffix(".json.tmp")
                    temp.write_text(json.dumps(match, indent=2, ensure_ascii=False), encoding="utf-8")
                    os.replace(temp, request_path)
            except (OSError, ValueError, TypeError) as exc:
                raise ValueError(f"难度已保存，但待开始比赛重新生成失败：{exc}") from exc
    return settings()


def persist_settings(cfg: dict) -> dict:
    _clean(cfg)
    SETTINGS_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


def cs2_is_live() -> bool:
    return bool(live_cs2_pids())


def require_cs2_closed(action: str = "改游戏文件") -> None:
    if cs2_is_live():
        raise ValueError(f"请先完全退出 CS2，再{action}。")


def game_levels_ok(csgo: Path) -> bool:
    # Compatibility field used by the existing UI. 1.5 has one generated pack.
    from .profiles import _template_text
    try:
        return all(bool(_template_text(level)) for level in DIFFICULTIES)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def sync_live_profiles() -> dict:
    return {"ok": True, "added": 0, "disabled": True,
            "msg": "1.5 不同步人物数据库；开始比赛时会生成并校验本场恰好 9 人。"}


def plugin_dir(csgo: Path) -> Path:
    return csgo / "addons" / "counterstrikesharp" / "plugins" / "CareerMatch"


def skins_plugin_src(cfg: dict | None = None) -> Path:
    cfg = cfg or settings()
    custom = Path(cfg.get("skins_source_path") or "")
    if _skins_pack(custom):
        return custom
    bundled = vendor_root() / "InventorySimulator"
    if _skins_pack(bundled):
        return bundled
    return custom


def _skins_pack(path: Path) -> bool:
    if not path.is_dir():
        return False
    return bool(_skins_plugin_dir(path))


def _skins_plugin_dir(root: Path) -> Path | None:
    for cand in (
        root / "plugins" / "InventorySimulator",
        root / "addons" / "counterstrikesharp" / "plugins" / "InventorySimulator",
        root,
    ):
        if (cand / "InventorySimulator.dll").is_file():
            return cand
    return None


def skins_gamedata_override() -> Path:
    path = save_root() / "skins_gamedata" / "inventory-simulator.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _skins_gamedata(root: Path) -> Path | None:
    override = skins_gamedata_override()
    if override.is_file():
        return override
    for cand in (
        root / "gamedata" / "inventory-simulator.json",
        root / "addons" / "counterstrikesharp" / "gamedata" / "inventory-simulator.json",
    ):
        if cand.is_file():
            return cand
    bundled = vendor_root() / "InventorySimulator" / "gamedata" / "inventory-simulator.json"
    if bundled.is_file():
        return bundled
    return None


GAMEDATA_REQUIRED = {
    "CAttributeList::SetOrAddAttributeValueByName",
    "CCSPlayerInventory::GetItemInLoadout",
    "GetItemSchema",
    "CCSPlayer_WeaponServices::DropWeapon",
}


def _validate_gamedata(blob: bytes) -> dict:
    try:
        data = json.loads(blob.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"gamedata 不是有效 JSON：{exc}") from exc
    if not isinstance(data, dict) or not GAMEDATA_REQUIRED.issubset(data):
        raise ValueError("gamedata 缺少 Inventory Simulator 必需键")
    signatures = offsets = 0
    for key, row in data.items():
        if not isinstance(row, dict):
            raise ValueError(f"gamedata 项 {key} 不是对象")
        if "signatures" in row:
            node = row["signatures"]
            if not isinstance(node, dict) or not isinstance(node.get("library"), str):
                raise ValueError(f"{key}.signatures 结构错误")
            if not all(isinstance(node.get(os_name), str) and node[os_name].strip() for os_name in ("windows", "linux")):
                raise ValueError(f"{key}.signatures 缺少平台值")
            signatures += 1
        elif "offsets" in row:
            node = row["offsets"]
            if not isinstance(node, dict) or not all(isinstance(node.get(os_name), int) for os_name in ("windows", "linux")):
                raise ValueError(f"{key}.offsets 缺少整数平台值")
            offsets += 1
        else:
            raise ValueError(f"{key} 既没有 signatures 也没有 offsets")
    if signatures == 0 or offsets == 0:
        raise ValueError("gamedata 必须同时包含 signatures 和 offsets")
    return data


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _atomic_replace(path: Path, blob: bytes, backup: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        _validate_gamedata(Path(raw).read_bytes())
        if backup is not None and path.is_file():
            shutil.copy2(path, backup)
        os.replace(raw, path)
    except BaseException:
        try:
            os.unlink(raw)
        except OSError:
            pass
        raise


def _gamedata_info(path: Path, source: str) -> dict:
    return {"source": source, "path": str(path), "exists": path.is_file(),
            "sha256": _sha256(path), "time": path.stat().st_mtime if path.is_file() else 0}


def gamedata_status(csgo: Path | None = None) -> dict:
    csgo = csgo or resolve_csgo_path(settings().get("csgo_path") or "")
    built = vendor_root() / "InventorySimulator" / "gamedata" / "inventory-simulator.json"
    cache = skins_gamedata_override()
    game = csgo / "addons" / "counterstrikesharp" / "gamedata" / "inventory-simulator.json"
    return {"bundled": _gamedata_info(built, "bundled"), "cached": _gamedata_info(cache, "official-cache"),
            "installed": _gamedata_info(game, "game"), "pending_install": cache.is_file() and _sha256(cache) != _sha256(game)}


def update_skins_gamedata() -> dict:
    """Pull the author's latest function signatures. Does not replace the DLL."""
    dest = skins_gamedata_override()
    last_err: Exception | None = None
    blob = b""
    for url in SKINS_GAMEDATA_URLS:
        try:
            with urllib.request.urlopen(url, timeout=25) as resp:
                blob = resp.read()
            _validate_gamedata(blob)
            last_err = None
            break
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            last_err = exc
            blob = b""
    if not blob:
        fallback = dest if dest.is_file() else _skins_gamedata(vendor_root() / "InventorySimulator")
        message = (
            f"下载或校验失败（{last_err}）。仍保留最后一份有效签名。"
            if fallback is not None else f"下载换肤签名失败：{last_err}。"
        )
        return {"ok": False, "status": "rejected", "msg": message, "versions": gamedata_status()}
    new_hash = hashlib.sha256(blob).hexdigest()
    cache_changed = not dest.is_file() or _sha256(dest) != new_hash
    if not cache_changed:
        status_name = "unchanged"
    else:
        _atomic_replace(dest, blob, dest.with_name("inventory-simulator.previous.json"))
        status_name = "cached"
    copied = False
    try:
        csgo = Path(settings().get("csgo_path") or "")
        if csgo.is_dir() and not cs2_is_live():
            gdest = csgo / "addons" / "counterstrikesharp" / "gamedata" / "inventory-simulator.json"
            game_changed = _sha256(gdest) != new_hash
            if game_changed:
                _atomic_replace(gdest, blob, gdest.with_name("inventory-simulator.previous.json"))
            copied = True
            status_name = "installed" if game_changed else status_name
        elif csgo.is_dir() and cs2_is_live() and _sha256(
            csgo / "addons" / "counterstrikesharp" / "gamedata" / "inventory-simulator.json"
        ) != new_hash:
            status_name = "cached"
    except OSError:
        copied = False
    msg = "已保存最新换肤签名。"
    if copied:
        msg += "并写入了游戏目录。完全退出 CS2 再开才会生效。"
    else:
        msg += "下次点「把换肤插件装进游戏」时会用这份。"
    return {"ok": True, "status": status_name, "sha256": new_hash, "msg": msg,
            "versions": gamedata_status()}


def skins_wanted(career=None) -> bool:
    if career is not None:
        return bool(getattr(career, "real_skins", False))
    path = save_file("career.json")
    if not path.is_file():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("real_skins"))
    except (OSError, ValueError):
        return False


def _plugin_live(csgo: Path, name: str) -> Path:
    return csgo / "addons" / "counterstrikesharp" / "plugins" / name


def _plugin_parked(csgo: Path, name: str) -> Path:
    return csgo / "addons" / "counterstrikesharp" / "plugins_off" / name


def _copy_tree(src: Path, dst: Path) -> int:
    copied = 0
    if not src.is_dir():
        return 0
    for item in src.rglob("*"):
        if item.is_dir() or item.suffix.lower() == ".pdb":
            continue
        dest = dst / item.relative_to(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest)
        copied += 1
    return copied


def _remove_plugin(csgo: Path, name: str) -> None:
    """Park a live plugin so the next CS2 boot will not load it."""
    live = _plugin_live(csgo, name)
    if not live.is_dir():
        return
    parked = _plugin_parked(csgo, name)
    parked.parent.mkdir(parents=True, exist_ok=True)
    try:
        if parked.exists():
            shutil.rmtree(parked)
        shutil.move(str(live), str(parked))
    except OSError:
        try:
            shutil.rmtree(live)
        except OSError:
            pass


def restore_bot_randomizer(csgo: Path) -> int:
    """Put BotRandomizer back even if a previous match parked it."""
    live = _plugin_live(csgo, "BotRandomizer")
    dll = live / "BotRandomizer.dll"
    sources = [
        _plugin_parked(csgo, "BotRandomizer"),
        Path(settings()["mod_source_path"])
        / "addons"
        / "counterstrikesharp"
        / "plugins"
        / "BotRandomizer",
    ]
    src = next((path for path in sources if (path / "BotRandomizer.dll").is_file()), None)
    if src is None:
        return 1 if dll.is_file() else 0
    return _copy_tree(src, live)


def install_skins_plugin(csgo: Path, career=None) -> int:
    """Player skins are optional. Bot cosmetics must stay loaded either way."""
    if skins_wanted(career):
        copied = _copy_skins_into(csgo)
    else:
        _remove_plugin(csgo, "InventorySimulator")
        _remove_plugin(csgo, "InvsimCareer")
        copied = 0
    # Always last: entering a match used to park this, which stripped bot paints.
    copied += restore_bot_randomizer(csgo)
    return copied


def _copy_skins_into(csgo: Path) -> int:
    src = skins_plugin_src()
    plugin_src = _skins_plugin_dir(src)
    if plugin_src is None:
        return 0
    copied = _copy_tree(plugin_src, _plugin_live(csgo, "InventorySimulator"))
    gamedata = _skins_gamedata(src)
    if gamedata is not None:
        dest = csgo / "addons" / "counterstrikesharp" / "gamedata" / "inventory-simulator.json"
        blob = gamedata.read_bytes()
        _validate_gamedata(blob)
        if _sha256(dest) != hashlib.sha256(blob).hexdigest():
            _atomic_replace(dest, blob, dest.with_name("inventory-simulator.previous.json"))
        copied += 1
    helper = vendor_root() / "InvsimCareer"
    if (helper / "InvsimCareer.dll").is_file():
        copied += _copy_tree(helper, _plugin_live(csgo, "InvsimCareer"))
    return copied


def install_skins_mod(csgo: Path | None = None) -> dict:
    """Install the optional skin plugin. Needs Bot Improver / CSS already in game."""
    require_cs2_closed("把换肤插件装进游戏")
    cfg = settings()
    csgo = resolve_csgo_path(csgo or cfg["csgo_path"])
    if not is_csgo_dir(csgo):
        raise FileNotFoundError(
            f"csgo 目录对不上：{csgo}。请指到 ...\\Counter-Strike Global Offensive\\game\\csgo，"
            "或填 Steam 里那层游戏根目录，保存时会自动补上 game\\csgo。"
        )
    if not css_installed(csgo):
        raise FileNotFoundError("请先把人机增强装进游戏，换肤插件挂在同一套 CounterStrikeSharp 上。")
    src = skins_plugin_src(cfg)
    if _skins_plugin_dir(src) is None:
        raise FileNotFoundError(
            "找不到换肤插件 DLL。生涯自带一份修过本地读取的 Inventory Simulator；"
            "也可在训练赛页填已编译插件的目录。"
        )
    files = _copy_skins_into(csgo)
    if files <= 0:
        raise FileNotFoundError("换肤插件没有拷进去。")
    return {"ok": True, "files": files, "msg": f"已把 {files} 个换肤文件装进游戏。完全退出 CS2 后再开才会加载。"}


def profiles_are_stale(csgo: Path) -> bool:
    """True when the bot database was rewritten after CS2 booted.

    The game mounts botprofile.vpk as a search path at startup, so a newer file
    on disk means the running game is still using the old names and difficulty.
    """
    started = cs2_started_at()
    if not started:
        return False
    live = csgo / "overrides" / "botprofile.vpk"
    return live.is_file() and live.stat().st_mtime > started


def installed_difficulty(csgo: Path, mod: Path) -> str:
    """Difficulty proven by the active VPK manifest and SHA-256."""
    manifest = active_manifest(csgo)
    return manifest.get("difficulty", "") if manifest.get("valid") else ""


def mod_installed(csgo: Path) -> bool:
    """Whether the mod's own files already live in the game folder."""
    return (
        (csgo / "addons" / "metamod").is_dir()
        and (csgo / "addons" / "counterstrikesharp").is_dir()
        and (csgo / "addons" / "BotHider").is_dir()
    )


def install_mod(csgo: Path | None = None, mod: Path | None = None) -> dict:
    """Copy only Bot Improver's runtime; career matches provide their own nine identities."""
    require_cs2_closed("把人机增强装进游戏")
    cfg = settings()
    csgo = resolve_csgo_path(csgo or cfg["csgo_path"])
    mod = Path(mod or cfg["mod_source_path"])
    if not is_csgo_dir(csgo):
        raise FileNotFoundError(
            f"csgo 目录对不上：{csgo}。请指到 ...\\Counter-Strike Global Offensive\\game\\csgo，"
            "或填 Steam 里那层游戏根目录，保存时会自动补上 game\\csgo。"
        )
    if not _improver_here(mod):
        raise FileNotFoundError(
            f"这不是完整的人机增强目录：{mod}。应能看到 addons\\metamod、"
            "addons\\counterstrikesharp 和 overrides。"
        )

    saved = csgo / "gameinfo.gi.career-backup"
    if (csgo / "gameinfo.gi").is_file() and not saved.exists():
        shutil.copy2(csgo / "gameinfo.gi", saved)

    files = 0
    for src in mod.rglob("*"):
        if src.is_dir() or src.suffix.lower() == ".exe":
            continue
        rel = src.relative_to(mod)
        rel_key = "/".join(part.lower() for part in rel.parts)
        # The enhancement plugins are reused; neither its BotProfile roster nor
        # BotHider's thousands-of-players identity list belongs to career mode.
        if "overrides" in [part.lower() for part in rel.parts] and src.name.lower() in (
            "botprofile.db", "botprofile.vpk"
        ):
            continue
        if rel_key == "addons/bothider/bot_info.json":
            continue
        dst = csgo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        files += 1
    files += _copy_career_match(csgo, mod)
    files += _copy_botbuy_patch(csgo)
    hook_competitive_cfg(csgo)
    apply_bothider_config(csgo, cfg["bot_identity"])
    return {
        "ok": True,
        "files": files,
        "msg": f"已把 {files} 个人机增强文件装进游戏。人物库未复制；每场开赛前生成 9 人档案。",
    }


def status() -> dict:
    cfg = settings()
    csgo = resolve_csgo_path(cfg["csgo_path"])
    if is_csgo_dir(csgo):
        cfg["csgo_path"] = str(csgo)
    mod = Path(cfg["mod_source_path"])
    levels = game_levels_ok(csgo)
    manifest = active_manifest(csgo) if csgo.is_dir() else {}
    applied = manifest.get("difficulty", "") if manifest.get("valid") else ""
    pending = bool(applied and cfg.get("difficulty") != applied)
    process_difficulty = ""
    if csgo.is_dir() and cs2_is_live() and manifest.get("valid"):
        active = csgo / "overrides" / "botprofile.vpk"
        if active.stat().st_mtime < cs2_started_at():
            process_difficulty = applied
    return {
        **cfg,
        "csgo_ok": csgo.is_dir(),
        "mod_ok": _improver_here(mod) or (mod.is_dir() and (mod / "overrides").is_dir()),
        "mod_installed": csgo.is_dir() and mod_installed(csgo),
        "levels_ok": levels,
        "steam_ok": Path(cfg["steam_exe"]).is_file(),
        "ready": csgo.is_dir() and mod.is_dir() and Path(cfg["steam_exe"]).is_file(),
        "cs2_live": bool(live_cs2_pids()),
        "difficulty_pending": pending,
        "difficulties": list(DIFFICULTIES),
        "aim_modes": list(AIM_MODES),
        "nade_modes": list(NADE_MODES),
        "identity_modes": list(IDENTITY_MODES),
        "installed_difficulty": applied if applied in DIFFICULTIES else "",
        "active_vpk_type": manifest.get("type", "career_match_9") if manifest else "",
        "match_nonce": manifest.get("nonce", ""),
        "profile_hash": manifest.get("manifest_hash", ""),
        "profile_hash_short": str(manifest.get("manifest_hash", ""))[:8],
        "profile_sync_count": int(manifest.get("count") or 0) if manifest.get("valid") else 0,
        "actual_difficulty": applied,
        "difficulty_model": manifest.get("difficulty_model", "") if manifest else "",
        "preset_source_hash": manifest.get("preset_source_hash", "") if manifest else "",
        "template_hash": manifest.get("template_hash", "") if manifest else "",
        "generated_difficulty": manifest.get("difficulty", "") if manifest else "",
        "cs2_process_difficulty": process_difficulty,
        "bot_profiles": manifest.get("bots", []) if manifest.get("valid") else [],
        "active_vpk_valid": bool(manifest.get("valid")),
        "active_vpk_error": manifest.get("error", ""),
        "skins_source_path": cfg.get("skins_source_path") or "",
        "skins_ok": _skins_pack(skins_plugin_src(cfg)),
        "skins_installed": csgo.is_dir()
        and (_plugin_live(csgo, "InventorySimulator") / "InventorySimulator.dll").is_file(),
        "gamedata": gamedata_status(csgo),
    }


# ------------------------------------------------------------------ processes


def _powershell(script: str) -> str:
    try:
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            text=True,
            errors="ignore",
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return ""


def live_cs2_pids() -> list[int]:
    """Even a small/starting process can load the VPK; never infer safety from RAM use."""
    out = _powershell(
        "(Get-Process -Name cs2 -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty Id) -join ','"
    )
    return [int(x) for x in out.split(",") if x.strip().isdigit()]


def kill_zombie_cs2() -> None:
    _powershell(
        "Get-Process -Name cs2 -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.WorkingSet64 -lt {LIVE_MEMORY_BYTES} }} | "
        "Stop-Process -Force -ErrorAction SilentlyContinue"
    )


def cs2_started_at() -> float:
    """Unix seconds when the running game started, 0 if it is not running."""
    out = _powershell(
        "(Get-Process -Name cs2 -ErrorAction SilentlyContinue | "
        "Sort-Object StartTime | Select-Object -First 1 -ExpandProperty StartTime | "
        "Get-Date -UFormat %s)"
    )
    try:
        return float(out.replace(",", ".").strip())
    except ValueError:
        return 0.0


def steam_running() -> bool:
    return bool(
        _powershell(
            "(Get-Process -Name steam -ErrorAction SilentlyContinue | Measure-Object).Count"
        ).strip()
        not in ("", "0")
    )


# ------------------------------------------------------------------ game files


def _pick_bots(roster: list[dict], want: int, used: set[str]) -> list[dict]:
    """Keep full career identity; the VPK generator assigns safe ASCII names."""
    from ..world.ability import playing_ability
    out: list[dict] = []
    for player in roster:
        if len(out) >= want:
            break
        name = player["name"]
        if name.lower() in used:
            continue
        used.add(name.lower())
        ability = playing_ability(player)
        form_delta = player.get("form_delta")
        if form_delta is None:
            # 1.4 stored form on an ability-like scale. Convert at the boundary.
            form_delta = float(player.get("form", ability)) - ability
        out.append({
            "player_id": str(player.get("player_id") or stable_player_id(name)),
            "display_name": name,
            "overall": ability,
            "form_delta": max(-10.0, min(10.0, float(form_delta))),
            "role": player.get("role") or "rifle",
            "stats": dict(player.get("stats") or {}),
        })
    return out


def build_request(my_team: dict, opp: dict, player_name: str, map_code: str, side: str) -> dict:
    used = {player_name.lower()}
    mates = _pick_bots(my_team["players"], 4, used)
    enemies = _pick_bots(opp["players"], 5, used)
    mine = {"team_id": my_team["id"], "name": my_team["name"], "logo": my_team["id"][:4], "players": mates}
    theirs = {"team_id": opp["id"], "name": opp["name"], "logo": opp["id"][:4], "players": enemies}
    side = "t" if side == "t" else "ct"
    ct, t = (mine, theirs) if side == "ct" else (theirs, mine)
    return {
        "schema_version": 2,
        "active": True,
        "map": map_code,
        "human_team": side,
        "ct": ct,
        "t": t,
        "player": player_name,
        "human_player_id": stable_player_id(player_name),
        # Always ask for a full 5v5 so the game backfills any name we dropped.
        "quota": 9,
        "nonce": uuid.uuid4().hex,
    }


def write_career_cfg(csgo: Path, match: dict, opts: dict | None = None) -> None:
    opts = _clean(dict(opts or DEFAULTS))
    cfg_dir = csgo / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    total = match.get("quota") or len(match["ct"]["players"]) + len(match["t"]["players"])
    # Safe to re-exec at halftime. Do NOT put warmup / bot_kick / bot_add /
    # mp_human_team here: competitive cfg runs again at the side swap, and
    # those commands yank everyone back to the opening sides.
    def cfg_text(value: object) -> str:
        # Source treats semicolons/newlines as command separators. Team labels
        # are cosmetic; identities remain the player_id values in the request.
        return "".join(ch for ch in str(value) if ch not in '\\";\r\n').strip()

    lines = [
        f"bh_identity_mode {opts['bot_identity']}",
        "mp_autoteambalance 0",
        "mp_limitteams 0",
        "mp_autokick 0",
        "bot_auto_vacate 0",
        "bot_join_after_player 0",
        "bot_quota_mode normal",
        f"bot_quota {total}",
        f"mp_teamname_1 \"{cfg_text(match['ct']['name'])}\"",
        f"mp_teamname_2 \"{cfg_text(match['t']['name'])}\"",
        f"mp_teamlogo_1 {match['ct']['logo']}",
        f"mp_teamlogo_2 {match['t']['logo']}",
        f"bot_aim {opts['bot_aim']}",
        f"bot_nades {opts['bot_nades']}",
    ]
    body = "\n".join(lines) + "\n"
    (cfg_dir / "career_rules.cfg").write_text(body, encoding="utf-8")
    (cfg_dir / "career_quick.cfg").write_text(body, encoding="utf-8")


def invsim_lines(steam_id: str = "") -> list[str]:
    # Do not write invsim_url here. Source cfg treats // as a comment, so
    # http://... becomes "http:" and the plugin cannot fetch anything.
    lines = [
        "invsim_fallback_team 1",
        "invsim_ws_enabled 1",
        "invsim_ws_immediately 0",
        "invsim_minmodels 1",
        "invsim_spray_enabled 0",
        "invsim_public_api_stattrak_increment 0",
        "invsim_public_api_spray_consume 0",
    ]
    digits = "".join(ch for ch in str(steam_id or "") if ch.isdigit())
    if digits:
        lines.append(f"invsim_only_steamid {digits}")
    return lines


def write_invsim_cfg(csgo: Path | None = None, steam_id: str = "") -> None:
    """Point Inventory Simulator at the career file. Never write http:// here."""
    if csgo is None:
        csgo = Path(settings()["csgo_path"])
    if not csgo.is_dir():
        return
    cfg_dir = csgo / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    inv_file = (
        csgo
        / "addons"
        / "counterstrikesharp"
        / "configs"
        / "plugins"
        / "InventorySimulator"
        / "inventories.json"
    )
    # Forward slashes so Source cfg never sees // (comment).
    file_arg = str(inv_file).replace("\\", "/")
    body = "\n".join([f'invsim_file "{file_arg}"', *invsim_lines(steam_id), ""])
    (cfg_dir / "invsim_career.cfg").write_text(body, encoding="ascii")
    for name in ("listenserver.cfg", "server.cfg"):
        path = cfg_dir / name
        existing = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        if "exec invsim_career.cfg" not in existing:
            prefix = existing.rstrip() + "\n" if existing.strip() else ""
            path.write_text(prefix + "exec invsim_career.cfg\n", encoding="utf-8")


def _neutralise_quota(line: str) -> str:
    """Stop the game mode cfg from filling the server with random bots.

    These lines run before ours. If they add ten random bots first, our named
    ones push the server over quota and the game kicks players mid-round.
    """
    if re.match(r"\s*bot_quota_mode\s+\S+", line):
        return "bot_quota_mode normal"
    if re.match(r"\s*bot_quota\s+\d+", line):
        return "bot_quota 0"
    return line


def _hook_cfg(path: Path) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    body = "\n".join(_neutralise_quota(line) for line in text.splitlines())
    body = body.replace("exec career_quick.cfg", "exec career_rules.cfg")
    if "exec career_rules.cfg" not in body:
        body = body.rstrip() + "\nexec career_rules.cfg"
    path.write_text(body + "\n", encoding="utf-8")


def hook_competitive_cfg(csgo: Path) -> None:
    cfg = csgo / "cfg"
    for name in (
        "gamemode_competitive.cfg",
        "gamemode_competitive_offline.cfg",
        "gamemode_casual.cfg",
        "gamemode_custom.cfg",
    ):
        _hook_cfg(cfg / name)


def apply_bothider_config(csgo: Path, identity: str = "player") -> None:
    root = csgo / "addons" / "BotHider"
    if not root.is_dir():
        return
    path = root / "config.json"
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
    data["identity_mode"] = identity if identity in IDENTITY_MODES else "player"
    data.setdefault("fake_ping", {"enabled": True, "min": 5, "max": 90})
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


def _copy_career_match(csgo: Path, mod_source: Path | None = None) -> int:
    """Verified deployment; a missing/locked DLL must never silently launch an old plugin."""
    require_cs2_closed("更新比赛回传插件")
    src = career_match_src(mod_source)
    dst = plugin_dir(csgo)
    return _copy_verified_plugin(src, dst, "CareerMatch")


def _copy_botbuy_patch(csgo: Path) -> int:
    require_cs2_closed("更新生涯买枪补丁")
    return _copy_verified_plugin(vendor_root() / "BotBuy", _plugin_live(csgo, "BotBuy"), "BotBuy")


def _copy_verified_plugin(src: Path, dst: Path, plugin_name: str) -> int:
    copied = 0
    names = (f"{plugin_name}.dll", f"{plugin_name}.deps.json")
    for name in names:
        if not (src / name).is_file():
            raise FileNotFoundError(f"比赛回传插件缺少 {name}，请使用完整的CS2联调包。")
    json.loads((src / names[1]).read_text(encoding='utf-8-sig'))
    dst.mkdir(parents=True, exist_ok=True)
    for name in names:
        target = dst / name
        digest = _sha256(src / name)
        if _sha256(target) == digest:
            continue
        handle, raw = tempfile.mkstemp(prefix=f'.{name}.',suffix='.tmp',dir=dst)
        os.close(handle)
        pending = Path(raw)
        try:
            shutil.copy2(src / name,pending)
            if _sha256(pending) != digest:
                raise OSError(f"{name} 复制校验失败")
            backup = target.with_name(name+'.career-backup')
            if target.is_file() and not backup.exists():
                shutil.copy2(target,backup)
            os.replace(pending,target)
            if _sha256(target) != digest:
                raise OSError(f"{name} 安装校验失败")
            copied += 1
        finally:
            pending.unlink(missing_ok=True)
    return copied


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
AVATAR_MAX_BYTES = 16 * 1024
STEAM_ID64_BASE = 76561197960265728


def _safe_avatar_source(team: dict) -> tuple[Path, str]:
    """Pick a curated/local team mark, falling back to our neutral avatar."""
    team_id = re.sub(r"[^a-z0-9-]", "", str(team.get("team_id") or "").lower())
    candidates = []
    if team_id:
        # A logo explicitly uploaded by the user is allowed only when it also
        # meets BotHider's small, static PNG contract.
        candidates.append((logo_dir() / f"{team_id}.png", "custom"))
        candidates.append((static_dir() / "team_avatars" / f"{team_id}.png", "team"))
    candidates.append((static_dir() / "team_avatars" / "default.png", "default"))
    for path, kind in candidates:
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        if 0 < len(payload) <= AVATAR_MAX_BYTES and payload.startswith(PNG_SIGNATURE):
            return path, kind
    raise FileNotFoundError("缺少安全的默认 Bot 头像资源")


def install_match_avatars(csgo: Path, match: dict) -> None:
    """Bind both teams to local PNGs before hashing the nine-bot request."""
    dst = plugin_dir(csgo) / "avatars"
    dst.mkdir(parents=True, exist_ok=True)
    nonce = re.sub(r"[^a-fA-F0-9]", "", str(match.get("nonce") or ""))[:16]
    for side in ("ct", "t"):
        source, kind = _safe_avatar_source(match[side])
        payload = source.read_bytes()
        target = dst / f"{nonce}-{side}.png"
        handle, raw = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=dst)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(raw, target)
        except BaseException:
            try:
                os.unlink(raw)
            except OSError:
                pass
            raise
        digest = hashlib.sha256(payload).hexdigest()
        # Forward slashes avoid Source command escaping while remaining a
        # valid absolute Windows path for BotHider.
        avatar_path = str(target.resolve()).replace("\\", "/")
        for player in match[side].get("players") or []:
            player.update({
                "avatar_path": avatar_path,
                "avatar_hash": digest,
                "avatar_kind": kind,
            })


def install_match_identities(csgo: Path, match: dict) -> dict:
    """Write exactly nine stable BotHider identities for the active career match.

    BotHider needs a distinct SteamID for each synthetic player; duplicate or
    missing IDs make CS2 collapse scoreboard rows and prevent avatar lookup.
    The per-match file replaces Bot Improver's large identity database.
    """
    bots = sorted(match.get("bots") or [], key=lambda row: str(row.get("player_id") or ""))
    if len(bots) != 9:
        raise ValueError(f"本场 BotHider 身份必须恰好为 9 人，当前为 {len(bots)} 人")
    ids = [str(bot.get("player_id") or "") for bot in bots]
    profiles = [str(bot.get("profile_name") or "") for bot in bots]
    if not all(ids) or len(set(ids)) != 9 or not all(profiles) or len(set(profiles)) != 9:
        raise ValueError("本场 BotHider 的 player_id 或 profile_name 不唯一")

    used: set[int] = set()
    players: dict[str, dict] = {}
    for bot in bots:
        digest = hashlib.sha256(("c2c-bot:" + bot["player_id"]).encode("utf-8")).digest()
        low = int.from_bytes(digest[:4], "little") & 0x7FFFFFFF
        for offset in range(9):
            account_id = 0x80000000 | ((low + offset) & 0x7FFFFFFF)
            if account_id not in used:
                break
        else:
            raise ValueError("无法为本场 Bot 分配唯一的合成 SteamID")
        used.add(account_id)
        steam_id = STEAM_ID64_BASE + account_id
        bot["steam_id"] = steam_id
        players[str(account_id)] = {
            # BotHider matches this against the botprofile name at spawn.  The
            # visible nickname is applied later by CareerMatch.
            "player_name": bot["profile_name"],
            "scoreboard_flair": 0,
        }

    # Side lists and match["bots"] normally share the same dictionaries, but
    # update by player_id as well so the JSON contract never relies on aliasing.
    steam_by_id = {bot["player_id"]: bot["steam_id"] for bot in bots}
    for side in ("ct", "t"):
        for bot in match.get(side, {}).get("players") or []:
            bot["steam_id"] = steam_by_id[str(bot.get("player_id") or "")]

    payload = {
        "players": players,
        "disabled_players": {},
    }
    target = csgo / "addons" / "BotHider" / "bot_info.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, raw = tempfile.mkstemp(prefix=".bot_info.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(json.dumps(payload, indent=4, ensure_ascii=True).encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(raw, target)
    except BaseException:
        try:
            os.unlink(raw)
        except OSError:
            pass
        raise
    return payload


def blank_result(map_code: str) -> dict:
    return {
        "schema_version": 2,
        "status": "pending",
        "map": map_code,
        "winner": "",
        "ct_score": 0,
        "t_score": 0,
        "ct_name": "",
        "t_name": "",
        "ended_at": "",
        "players": [],
    }


def prepare_game(
    csgo: Path,
    mod_source: Path,
    match: dict,
    opts: dict | None = None,
    teams: list[dict] | None = None,
    career=None,
) -> None:
    opts = _clean(dict(opts or DEFAULTS))
    csgo = resolve_csgo_path(csgo)
    if not is_csgo_dir(csgo):
        raise FileNotFoundError(
            f"csgo_path 对不上：{csgo}。请指到 ...\\game\\csgo，"
            "或填 Steam 游戏根目录，保存时会自动补上。"
        )
    if not mod_source.is_dir():
        raise FileNotFoundError(f"找不到 mod 目录：{mod_source}")
    require_cs2_closed("生成并安装本场 9 人 BotProfile")
    if not mod_installed(csgo):
        raise ValueError("游戏中缺少人机增强运行组件，请先在游戏设置安装人机增强。")
    _copy_career_match(csgo, mod_source)
    _copy_botbuy_patch(csgo)
    match["bot_identity"] = opts["bot_identity"]
    want = opts["difficulty"]
    install_match_avatars(csgo, match)
    manifest = generate_match_vpk(csgo, match, want)
    if not manifest.get("manifest_hash") or manifest.get("count") != 9:
        raise ValueError("本场 BotProfile 清单校验失败，已阻止开赛")
    install_match_identities(csgo, match)
    try:
        n = install_skins_plugin(csgo, career)
        if skins_wanted(career) and n:
            from ..career import skins as skinmod

            skinmod.sync_live(career)
    except OSError:
        pass

    dst = plugin_dir(csgo)
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "match_request.json").write_text(
        json.dumps(match, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    blank = json.dumps(blank_result(match["map"]), indent=2, ensure_ascii=False)
    (dst / "match_result.json").write_text(blank, encoding="utf-8")
    (dst / "match_result.best.json").write_text(blank, encoding="utf-8")
    save_file("cs2_last.json").write_text(blank, encoding="utf-8")
    write_career_cfg(csgo, match, opts)
    hook_competitive_cfg(csgo)
    apply_bothider_config(csgo, opts["bot_identity"])

    withbots = mod_source / "backup" / "WithBots" / "gameinfo.gi"
    if withbots.exists():
        shutil.copy2(withbots, csgo / "gameinfo.gi")


def launch_cs2(steam_exe: str) -> None:
    exe = Path(steam_exe)
    if not exe.is_file():
        raise FileNotFoundError(f"找不到 steam.exe：{steam_exe}")
    if not steam_running():
        subprocess.Popen([str(exe)], cwd=str(exe.parent))
        for _ in range(20):
            if steam_running():
                time.sleep(3)
                break
            time.sleep(1)
    if live_cs2_pids():
        return "already_running"
    # Only -insecure, same as the official panel. A +map here blacks out CS2.
    # -condebug mirrors the console into csgo/console.log for diagnosing launches.
    subprocess.Popen(
        [str(exe), "-applaunch", "730", "-insecure", "-condebug"], cwd=str(exe.parent)
    )
    return "launched"


# ------------------------------------------------------------------ public API


DIFFICULTY_LABEL = {"Low": "简单", "Medium": "中等", "High": "极难"}
NADE_LABEL = {"off": "关闭", "less": "偏少", "normal": "正常", "more": "偏多", "max": "最多"}
AIM_LABEL = {"head": "爆头优先", "mixed": "混合", "body": "身体优先"}
IDENTITY_LABEL = {"player": "真人身份", "bot": "显示 BOT"}


def start_match(
    my_team: dict,
    opp: dict,
    player_name: str,
    map_code: str,
    side: str,
    teams: list[dict] | None = None,
    career=None,
    *, purpose: str = "series",
) -> dict:
    cfg = settings()
    if not Path(cfg['steam_exe']).is_file():
        raise FileNotFoundError("找不到 steam.exe，请先在游戏设置保存有效路径。")
    match = build_request(my_team, opp, player_name, map_code, side)
    prepare_game(
        Path(cfg["csgo_path"]),
        Path(cfg["mod_source_path"]),
        match,
        cfg,
        teams if teams is not None else [my_team, opp],
        career,
    )
    state = launch_cs2(cfg["steam_exe"])
    if purpose == "training" and career is not None:
        career.remember_training(match)
    you_side = "CT" if match["human_team"] == "ct" else "T"
    tune = (
        f"难度{DIFFICULTY_LABEL.get(cfg['difficulty'], cfg['difficulty'])}"
        f" · 瞄准{AIM_LABEL.get(cfg['bot_aim'], cfg['bot_aim'])}"
        f" · 道具{NADE_LABEL.get(cfg['bot_nades'], cfg['bot_nades'])}"
        f" · {IDENTITY_LABEL.get(cfg['bot_identity'], cfg['bot_identity'])}"
        f" · Bot档案 9/9 · {match['bot_profile']['short_hash']}"
    )
    tip = f"CS2 正在启动。进游戏后选：与机器人游戏 → 竞技 → {map_code}。"
    return {
        "ok": True,
        "match": match,
        "already_running": state == "already_running",
        "msg": (
            f"{tip} 你是 {player_name}，{you_side} 方 {my_team['name']}，"
            f"对手 {opp['name']}。{tune}。"
        ),
    }


def _load_result_file(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _remember_result(data: dict) -> None:
    if result_quality(data) < 1:
        return
    path = save_file("cs2_last.json")
    old = _load_result_file(path)
    if result_quality(data) <= result_quality(old):
        return
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_result(request_nonce: str | None = None) -> dict:
    cfg = settings()
    plugin = plugin_dir(Path(cfg["csgo_path"]))
    candidates = [
        _load_result_file(plugin / "match_result.json"),
        _load_result_file(plugin / "match_result.best.json"),
        _load_result_file(save_file("cs2_last.json")),
    ]
    # A higher-scoring previous map must not shadow this request's result.
    if request_nonce:
        candidates = [r for r in candidates if r and r.get('request_nonce') == request_nonce]
    data = pick_better_result(*candidates)
    if result_quality(data) > 0:
        _remember_result(data)
        if data.get("status") == "finished" and data.get("ended_at"):
            _archive(data)
    return data


def _archive(result: dict) -> None:
    out = save_file("cs2_matches.json")
    rows = []
    if out.exists():
        try:
            rows = json.loads(out.read_text(encoding="utf-8"))
        except ValueError:
            rows = []
    if any(r.get("ended_at") == result.get("ended_at") for r in rows):
        return
    rows.append(result)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def history() -> list[dict]:
    out = save_file("cs2_matches.json")
    if not out.exists():
        return []
    try:
        return json.loads(out.read_text(encoding="utf-8"))
    except ValueError:
        return []
