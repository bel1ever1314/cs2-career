# coding=utf-8
"""Hand a career match over to CS2 with named bots, then read the result back.

Needs the CS2 Bot Improver mod folder (CounterStrikeSharp + BotHider).
CareerMatch is bundled under vendor/ and copied in when the mod is installed.
Paths live in the save folder so a packaged build can be pointed at any install.
"""

from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

from ..paths import frozen, save_file, vendor_root
from .profiles import build_profile_vpk, seed_mod_profiles

SETTINGS_PATH = save_file("cs2.json")

DEFAULTS = {
    "steam_exe": "",
    "csgo_path": "",
    "mod_source_path": "",
    # Bot Improver knobs. Difficulty is a whole botprofile.vpk; aim and nades
    # are plugin commands that reset to their defaults every launch.
    "difficulty": "Medium",
    "bot_aim": "mixed",
    "bot_nades": "normal",
    # "player" drops the BOT tag: managed bots publish a name, SteamID and ping.
    "bot_identity": "player",
    "applied_difficulty": "",
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
    for key, val in patch.items():
        if key not in DEFAULTS or not val:
            continue
        if key == "csgo_path":
            cfg[key] = str(resolve_csgo_path(val))
        else:
            cfg[key] = val
    _clean(cfg)
    SETTINGS_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


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
    return all((csgo / "overrides" / lv / "botprofile.vpk").is_file() for lv in DIFFICULTIES)


def apply_live_difficulty(csgo: Path, level: str) -> None:
    """Copy the selected pack onto the VPK CS2 mounts. File copy only, no repack."""
    if level not in DIFFICULTIES:
        level = "Medium"
    src = csgo / "overrides" / level / "botprofile.vpk"
    if not src.is_file():
        raise FileNotFoundError("游戏目录里没有三档人机库。请先把人机增强装进游戏。")
    dst = csgo / "overrides" / "botprofile.vpk"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    cfg = settings()
    cfg["applied_difficulty"] = level
    persist_settings(cfg)


def sync_live_profiles() -> dict:
    require_cs2_closed("同步人机名单")
    cfg = settings()
    csgo = Path(cfg["csgo_path"])
    if not csgo.is_dir():
        raise FileNotFoundError("找不到 CS2 的 game\\csgo 目录。")
    if not game_levels_ok(csgo):
        raise FileNotFoundError("游戏目录里没有 Low/Medium/High。请先把人机增强装进游戏。")
    from .profiles import sync_overrides

    report = sync_overrides(csgo / "overrides", write=True, live_level=cfg["difficulty"])
    cfg = settings()
    cfg["applied_difficulty"] = cfg["difficulty"]
    persist_settings(cfg)
    added = int(report.get("added") or 0)
    if added:
        msg = f"已写入 game\\csgo\\overrides，数据包里新补了 {added} 个名字。完全退出 CS2 再开才会读到。"
    else:
        msg = "数据包里的名字游戏库都已有，没有新的要补。"
    return {"ok": True, "added": added, "msg": msg, "report": report}


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


def _skins_gamedata(root: Path) -> Path | None:
    for cand in (
        root / "gamedata" / "inventory-simulator.json",
        root / "addons" / "counterstrikesharp" / "gamedata" / "inventory-simulator.json",
    ):
        if cand.is_file():
            return cand
    return None


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
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gamedata, dest)
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
    """Last difficulty we copied onto the live VPK, not a file-size guess."""
    applied = settings().get("applied_difficulty") or ""
    if applied in DIFFICULTIES:
        return applied
    return ""


def mod_installed(csgo: Path) -> bool:
    """Whether the mod's own files already live in the game folder."""
    return (
        (csgo / "addons" / "metamod").is_dir()
        and (csgo / "addons" / "counterstrikesharp").is_dir()
        and (csgo / "addons" / "BotHider").is_dir()
    )


def install_mod(csgo: Path | None = None, mod: Path | None = None) -> dict:
    """Copy Bot Improver into game/csgo, then sync player_stats into that copy."""
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
        dst = csgo / src.relative_to(mod)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        files += 1
    files += _copy_career_match(csgo, mod)
    hook_competitive_cfg(csgo)
    apply_bothider_config(csgo, cfg["bot_identity"])
    extra = ""
    try:
        synced = sync_live_profiles()
        extra = " " + synced["msg"]
    except (OSError, ValueError) as exc:
        extra = f" 人机增强已装上，但名单同步失败：{exc}"
    return {
        "ok": True,
        "files": files,
        "msg": f"已把 {files} 个人机增强文件装进游戏。{extra}",
    }


def status() -> dict:
    cfg = settings()
    csgo = resolve_csgo_path(cfg["csgo_path"])
    if is_csgo_dir(csgo):
        cfg["csgo_path"] = str(csgo)
    mod = Path(cfg["mod_source_path"])
    levels = csgo.is_dir() and game_levels_ok(csgo)
    applied = cfg.get("applied_difficulty") or ""
    pending = bool(cfg.get("difficulty") and applied and cfg["difficulty"] != applied)
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
        "difficulties": [d for d in DIFFICULTIES if (mod / "overrides" / d / "botprofile.vpk").is_file()]
        or list(DIFFICULTIES),
        "aim_modes": list(AIM_MODES),
        "nade_modes": list(NADE_MODES),
        "identity_modes": list(IDENTITY_MODES),
        "installed_difficulty": applied if applied in DIFFICULTIES else "",
        "skins_source_path": cfg.get("skins_source_path") or "",
        "skins_ok": _skins_pack(skins_plugin_src(cfg)),
        "skins_installed": csgo.is_dir()
        and (_plugin_live(csgo, "InventorySimulator") / "InventorySimulator.dll").is_file(),
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
    """Only count a real running game. A 36 KB leftover cs2.exe is not one."""
    out = _powershell(
        "(Get-Process -Name cs2 -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.WorkingSet64 -ge {LIVE_MEMORY_BYTES} }} | "
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
        f"Where-Object {{ $_.WorkingSet64 -ge {LIVE_MEMORY_BYTES} }} | "
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


def _pick_bots(roster: list[dict], want: int, used: set[str]) -> list[str]:
    """CS2 refuses a bot whose name is already on the server, so keep them unique."""
    out: list[str] = []
    for player in roster:
        if len(out) >= want:
            break
        name = player["name"]
        if name.lower() in used:
            continue
        used.add(name.lower())
        out.append(name)
    return out


def build_request(my_team: dict, opp: dict, player_name: str, map_code: str, side: str) -> dict:
    used = {player_name.lower()}
    mates = _pick_bots(my_team["players"], 4, used)
    enemies = _pick_bots(opp["players"], 5, used)
    mine = {"name": my_team["name"], "logo": my_team["id"][:4], "players": mates}
    theirs = {"name": opp["name"], "logo": opp["id"][:4], "players": enemies}
    side = "t" if side == "t" else "ct"
    ct, t = (mine, theirs) if side == "ct" else (theirs, mine)
    return {
        "active": True,
        "map": map_code,
        "human_team": side,
        "ct": ct,
        "t": t,
        "player": player_name,
        # Always ask for a full 5v5 so the game backfills any name we dropped.
        "quota": 9,
    }


def write_career_cfg(csgo: Path, match: dict, opts: dict | None = None) -> None:
    opts = _clean(dict(opts or DEFAULTS))
    cfg_dir = csgo / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"bh_identity_mode {opts['bot_identity']}",
        "mp_autoteambalance 0",
        "mp_limitteams 0",
        "mp_autokick 0",
        "bot_auto_vacate 0",
        "bot_join_after_player 0",
        f"mp_human_team {match['human_team']}",
        # Kicking bots during a live round hands the other side a free round,
        # so drop into warmup first and do the whole swap in there.
        f"mp_warmuptime {WARMUP_SECONDS}",
        f"mp_warmuptime_all_players_connected {WARMUP_SECONDS - 10}",
        "mp_warmup_pausetimer 0",
        "mp_warmup_start",
        "bot_kick",
        "bot_quota_mode normal",
        "bot_quota 0",
    ]
    for name in match["ct"]["players"]:
        lines.append(f'bot_add_ct "{name}"')
    for name in match["t"]["players"]:
        lines.append(f'bot_add_t "{name}"')
    total = match.get("quota") or len(match["ct"]["players"]) + len(match["t"]["players"])
    lines += [
        f"bot_quota {total}",
        "bot_quota_mode normal",
        f"mp_teamname_1 \"{match['ct']['name']}\"",
        f"mp_teamname_2 \"{match['t']['name']}\"",
        f"mp_teamlogo_1 {match['ct']['logo']}",
        f"mp_teamlogo_2 {match['t']['logo']}",
        # Plugin presets reset on every launch, so restate them here.
        f"bot_aim {opts['bot_aim']}",
        f"bot_nades {opts['bot_nades']}",
    ]
    (cfg_dir / "career_quick.cfg").write_text("\n".join(lines) + "\n", encoding="ascii")


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
    if "exec career_quick.cfg" not in body:
        body = body.rstrip() + "\nexec career_quick.cfg"
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
    """Drop the career match plugin next to CounterStrikeSharp, if present."""
    src = career_match_src(mod_source)
    dst = plugin_dir(csgo)
    copied = 0
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("CareerMatch.dll", "CareerMatch.deps.json"):
        if (src / name).is_file():
            shutil.copy2(src / name, dst / name)
            copied += 1
    return copied


def blank_result(map_code: str) -> dict:
    return {
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


def difficulty_vpk(mod_source: Path, level: str) -> Path:
    """Each difficulty is its own botprofile.vpk under overrides/<Level>/."""
    picked = mod_source / "overrides" / level / "botprofile.vpk"
    if picked.is_file():
        return picked
    return mod_source / "overrides" / "botprofile.vpk"


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
    if not game_levels_ok(csgo):
        raise FileNotFoundError("游戏目录里没有三档人机库。请先把人机增强装进游戏。")
    if not mod_source.is_dir():
        raise FileNotFoundError(f"找不到 mod 目录：{mod_source}")

    want = opts["difficulty"]
    applied = settings().get("applied_difficulty") or ""
    if cs2_is_live() and applied and applied != want:
        raise ValueError(
            f"难度已改为{DIFFICULTY_LABEL.get(want, want)}，但 CS2 还开着，仍是"
            f"{DIFFICULTY_LABEL.get(applied, applied)}。请完全退出后再进。"
        )
    if not cs2_is_live():
        apply_live_difficulty(csgo, want)
    try:
        n = install_skins_plugin(csgo, career)
        if skins_wanted(career) and n:
            from ..career import skins as skinmod

            skinmod.sync_live(career)
    except OSError:
        pass

    dst = plugin_dir(csgo)
    dst.mkdir(parents=True, exist_ok=True)
    _copy_career_match(csgo, mod_source)

    (dst / "match_request.json").write_text(
        json.dumps(match, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (dst / "match_result.json").write_text(
        json.dumps(blank_result(match["map"]), indent=2, ensure_ascii=False), encoding="utf-8"
    )
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
    kill_zombie_cs2()
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
) -> dict:
    cfg = settings()
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
    you_side = "CT" if match["human_team"] == "ct" else "T"
    tune = (
        f"难度{DIFFICULTY_LABEL.get(cfg['difficulty'], cfg['difficulty'])}"
        f" · 瞄准{AIM_LABEL.get(cfg['bot_aim'], cfg['bot_aim'])}"
        f" · 道具{NADE_LABEL.get(cfg['bot_nades'], cfg['bot_nades'])}"
        f" · {IDENTITY_LABEL.get(cfg['bot_identity'], cfg['bot_identity'])}"
    )
    if state == "already_running":
        tip = (
            f"对局文件已写入。CS2 还开着，请在游戏里重新选："
            f"与机器人游戏 → 竞技 → {map_code}。"
        )
        if profiles_are_stale(Path(cfg["csgo_path"])):
            tip += "注意：机器人名单和难度是 CS2 启动时读的，这次改动要退出 CS2 重开才生效。"
    else:
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


def read_result() -> dict:
    cfg = settings()
    path = plugin_dir(Path(cfg["csgo_path"])) / "match_result.json"
    if not path.exists():
        return {"status": "none"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {"status": "none"}
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
