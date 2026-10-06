# coding=utf-8
"""Generate a self-contained 9-Bot player or 10-Bot observer match pack.

Match identities always come from the career roster. Template parameters come
from the bundled preset or an explicitly selected user VPK; its roster is not
copied and the source VPK is never overwritten.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import struct
import tempfile
from pathlib import Path
from zlib import crc32

from ..paths import save_root
from . import bot_behavior, improver_presets

VPK_SIGNATURE = 0x55AA1234
ENTRY_NAME = "botprofile"
ENTRY_EXT = "db"
NO_ARCHIVE = 0x7FFF
MATCH_VPK = 'career_botprofile.vpk'
LEVELS = ("Low", "Medium", "High")
PROFILE_RE = re.compile(r'^\S+\s+"(C2C_[A-Za-z0-9_]+)"\s*$', re.MULTILINE)
ROLE_STYLE = {
    "awp": ("SniperPro", "SniperPersonality"),
    # Entry is a career position, not an SMG-only loadout. Keep the aggressive
    # behavior while preferring affordable rifles over P90/MAC-10.
    "entry": ("RiflePro", "RusherPersonality"),
    "lurk": ("RiflePro", "CamperPersonality"),
    "support": ("RiflePro", "RiflePersonality"),
    "igl": ("RiflePro", "RiflePersonality"),
    "rifle": ("RiflePro", "RiflePersonality"),
}


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def stable_player_id(name: str) -> str:
    folded = re.sub(r"[^a-z0-9]+", "_", (name or "").casefold()).strip("_")[:18]
    digest = hashlib.sha256((name or "").strip().casefold().encode()).hexdigest()[:10]
    return f"p_{folded or 'player'}_{digest}"


def profile_name(player_id: str) -> str:
    return "C2C_" + re.sub(r"[^A-Za-z0-9_]", "_", player_id or "")[:42]


def effective_strength(overall: float, form_delta: float, difficulty: str) -> float:
    if difficulty not in LEVELS:
        raise ValueError(f"未知难度：{difficulty}")
    if not all(math.isfinite(float(v)) for v in (overall, form_delta)):
        raise ValueError('生涯能力和状态必须是有限数值')
    # Difficulty selects upstream tuning; career strength selects its tier.
    return round(clamp(float(overall) + .5 * float(form_delta), 45, 100), 3)


def classify_tier(overall: float, role: str = "rifle", stats: dict | None = None) -> str:
    value, role = float(overall), (role or "rifle").lower()
    if value < 65:
        if role == "entry":
            return "RankDuelist"
        if role in ("awp", "support", "igl"):
            return "RankOthers"
        return "RankRifler"
    if value < 75:
        return "ProSlow"
    if value < 85:
        return "ProSteady"
    if value < 90:
        stats = stats or {}
        fast = float(stats.get("entrying") or 0) + float(stats.get("opening") or 0)
        precise = float(stats.get("firepower") or 0) + float(stats.get("clutching") or 0)
        return "ProFast" if fast >= precise else "ProPrecise"
    return "ProTop"


def bot_parameters(strength: float, overall: float, difficulty: str = 'Medium',
                   role: str = 'rifle', stats: dict | None = None) -> dict[str, float | int | str]:
    """Original anonymous tier parameters, selected by current career strength.

    ``overall`` remains accepted for older callers, but does not add a second
    star bonus. Difficulty changes the base tuning, never the career tier.
    """
    if not math.isfinite(float(strength)):
        raise ValueError('Bot 强度必须是有限数值')
    s = clamp(float(strength), 45, 100)
    return improver_presets.parameters(difficulty, classify_tier(s, role, stats), s)


def _profile_block(bot: dict) -> str:
    weapon, personality = ROLE_STYLE.get(bot["role"], ROLE_STYLE["rifle"])
    chain = bot.get('template_chain') or f'{bot["tier"]}+{weapon}+{personality}'
    lines = [f'{chain} "{bot["profile_name"]}"']
    lines += [f"    {key} = {value}" for key, value in bot["parameters"].items()]
    if not bot.get('template_chain'):
        lines.append(f"    VoicePitch = {90 + crc32(bot['player_id'].encode('ascii')) % 21}")
    lines += ["End", ""]
    return "\n".join(lines)


def expected_bot_count(match: dict) -> int:
    if match.get('observer') is True:
        if match.get('human_player_id') or any(len(match.get(side, {}).get('players') or []) != 5 for side in ('ct','t')):
            raise ValueError('观察者模式必须是两边各 5 个 Bot，不能绑定真人选手')
        return 10
    return 9


def prepare_bots(match: dict, difficulty: str) -> list[dict]:
    from ..arena_roles import validate_tactical_abilities
    rows: list[dict] = []
    for side in ("ct", "t"):
        for source in match.get(side, {}).get("players") or []:
            if not isinstance(source, dict):
                raise ValueError("1.5 比赛请求必须使用结构化 Bot 身份")
            display = str(source.get("display_name") or source.get("name") or "").strip()
            pid = str(source.get("player_id") or stable_player_id(display))
            overall = float(source.get("overall", source.get("ability", 70)))
            form_delta = float(source.get("form_delta", 0))
            role = str(source.get("role") or "rifle").lower()
            strength = effective_strength(overall, form_delta, difficulty)
            stats = dict(source.get('stats') or {})
            tier = classify_tier(strength, role, stats)
            row = {
                "player_id": pid,
                "profile_name": profile_name(pid),
                "display_name": display,
                "side": side,
                "overall": round(overall, 3),
                "form_delta": round(form_delta, 3),
                "effective_strength": strength,
                "role": role,
                "tier": tier,
                "stats": stats,
                "aim_preset": improver_presets.aim_band(difficulty, tier, strength),
                # CareerMatch verifies this local PNG again before asking
                # BotHider to publish it.  Every bot gets either a team crest
                # or our bundled neutral avatar, never an arbitrary identity.
                "avatar_path": str(source.get("avatar_path") or ""),
                "avatar_hash": str(source.get("avatar_hash") or ""),
                "avatar_kind": str(source.get("avatar_kind") or "default"),
            }
            row["parameters"] = bot_parameters(strength, overall, difficulty, role, stats)
            if "tactical_abilities" in source:
                row["tactical_abilities"] = validate_tactical_abilities(source["tactical_abilities"])
            row["profile_hash"] = hashlib.sha256(_profile_block(row).encode()).hexdigest()
            if not _avatar_valid(row):
                raise ValueError(f"{pid} 没有通过校验的本地安全头像")
            rows.append(row)
    ids, names = [r["player_id"] for r in rows], [r["profile_name"] for r in rows]
    count = expected_bot_count(match)
    if len(rows) != count:
        raise ValueError(f"本场必须恰好有 {count} 个 Bot，当前为 {len(rows)} 个")
    if len(set(ids)) != count or len(set(names)) != count:
        raise ValueError("本场 Bot 的 player_id 或 profile_name 重复")
    return rows


def _template_text(difficulty: str = 'Medium') -> str:
    text = improver_presets.preset(difficulty)['text']
    required = ("Default", "RankRifler", "RankDuelist", "RankOthers", "ProSlow", "ProSteady", "ProFast", "ProPrecise", "ProTop", "RiflePro", "SniperPro", "Rusher", "Camper", "RiflePersonality", "SniperPersonality", "RusherPersonality", "CamperPersonality")
    missing = [n for n in required if not re.search(rf"(?m)^(?:Template )?{re.escape(n)}\b", text)]
    if missing:
        raise ValueError("BotProfile 模板缺失：" + ", ".join(missing))
    return text.rstrip() + "\n\n"


def vpk_bytes(db_text: str, resources: dict[str, bytes] | None = None) -> bytes:
    """Pack our roster and behavior resources at the supported resource paths."""
    files = {ENTRY_NAME + '.' + ENTRY_EXT: db_text.encode('utf-8')}
    for path, payload in (resources or {}).items():
        if path not in bot_behavior.RESOURCE_PATHS or not isinstance(payload, bytes) or not payload or len(payload) > 64 * 1024:
            raise ValueError('VPK 只允许已审核的 Bot 行为脚本。')
        files[path] = payload
    groups = {}
    for path, payload in files.items():
        folder, _, name = path.rpartition('/')
        stem, ext = name.rsplit('.', 1)
        groups.setdefault(ext, {}).setdefault(folder or ' ', {})[stem] = payload
    entries, chunks, offset = [], [], 0
    for ext, folders in sorted(groups.items()):
        entries.append(ext.encode() + b'\0')
        for folder, names in sorted(folders.items()):
            entries.append(folder.encode() + b'\0')
            for name, payload in sorted(names.items()):
                entries.append(name.encode() + b'\0' + struct.pack('<IHHIIH',
                    crc32(payload), 0, NO_ARCHIVE, offset, len(payload), 0xFFFF))
                chunks.append(payload)
                offset += len(payload)
            entries.append(b'\0')
        entries.append(b'\0')
    entries.append(b'\0')
    tree, data = b''.join(entries), b''.join(chunks)
    header = struct.pack("<IIIIIII", VPK_SIGNATURE, 2, len(tree), len(data), 0, 48, 0)
    body = header + tree + data
    checksummed = body + hashlib.md5(tree).digest() + hashlib.md5(b"").digest()
    return checksummed + hashlib.md5(checksummed).digest()


def write_vpk(dst: Path, db_text: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(vpk_bytes(db_text))


def read_db(vpk: Path) -> str:
    blob = vpk.read_bytes()
    sig, version, tree_size = struct.unpack_from("<III", blob, 0)
    if sig != VPK_SIGNATURE:
        raise ValueError(f"不是 VPK 文件：{vpk}")
    head, cursor = (12 if version == 1 else 28), (12 if version == 1 else 28)
    def read_string() -> str:
        nonlocal cursor
        end = blob.index(b"\0", cursor)
        value = blob[cursor:end].decode("utf-8", "replace")
        cursor = end + 1
        return value
    while True:
        ext = read_string()
        if not ext:
            break
        while True:
            folder = read_string()
            if not folder:
                break
            while True:
                name = read_string()
                if not name:
                    break
                _crc, preload, _archive, offset, length, _term = struct.unpack_from("<IHHIIH", blob, cursor)
                cursor += 18 + preload
                if name == ENTRY_NAME and ext == ENTRY_EXT:
                    start = head + tree_size + offset
                    return blob[start:start + length].decode("utf-8", "replace")
    raise ValueError(f"VPK 里没有 botprofile.db：{vpk}")


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(raw, path)
    except BaseException:
        try:
            os.unlink(raw)
        except OSError:
            pass
        raise


def _manifest_hash(manifest: dict) -> str:
    """Cross-language contract digest; CareerMatch recomputes these lines."""
    lines = [
        f"schema_version={int(manifest['schema_version'])}",
        f"type={manifest['type']}",
        f"nonce={manifest['nonce']}",
        f"difficulty={manifest['difficulty']}",
        f"count={int(manifest['count'])}",
        f"vpk_sha256={manifest['vpk_sha256']}",
    ]
    if manifest.get('difficulty_model'):
        lines += [f"difficulty_model={manifest['difficulty_model']}",
                  f"preset_source_hash={manifest['preset_source_hash']}",
                  f"template_hash={manifest['template_hash']}"]
    if manifest.get('vpk_file'):
        lines.append(f"vpk_file={manifest['vpk_file']}")
    for bot in sorted(manifest.get("bots") or [], key=lambda row: row["player_id"]):
        lines.append(
            "bot=" + "|".join(str(bot[key]) for key in (
                "player_id", "profile_name", "side", "profile_hash", "avatar_hash"
            ))
        )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def generate_match_vpk(csgo: Path, match: dict, difficulty: str, cache_root: Path | None = None,
                       *, custom_source: str = '') -> dict:
    bots = prepare_bots(match, difficulty)
    count = expected_bot_count(match)
    profile_type = 'observer_match_10' if count == 10 else 'career_match_9'
    preset = improver_presets.preset(difficulty)
    template, resources, model = _template_text(difficulty), bot_behavior.resources(difficulty), improver_presets.MODEL
    if custom_source:
        from . import custom_profiles
        if Path(custom_source).resolve() == (csgo / 'overrides' / MATCH_VPK).resolve():
            raise ValueError('自定义来源请选择你自己的 VPK，不要选择程序生成的 career_botprofile.vpk。')
        preset = custom_profiles.load(custom_source)
        template, model = preset['text'], custom_profiles.MODEL
        resources.update(preset['resources'])
        for bot in bots:
            bot['template_chain'] = custom_profiles.chain(bot, preset['templates'])
            bot['parameters'] = {}
            bot['aim_preset'] = 'Custom'
            bot['profile_hash'] = hashlib.sha256(_profile_block(bot).encode()).hexdigest()
    db_text = template + "".join(_profile_block(bot) for bot in bots)
    if PROFILE_RE.findall(db_text) != [b["profile_name"] for b in bots]:
        raise ValueError("生成后的 BotProfile 清单与请求不一致")
    payload = vpk_bytes(db_text, resources)
    vpk_sha = hashlib.sha256(payload).hexdigest()
    manifest = {
        "schema_version": 2, "type": profile_type, "nonce": match["nonce"], "difficulty": difficulty, "count": count,
        "difficulty_model": model, "vpk_file": MATCH_VPK,
        "preset_source_hash": preset['source_hash'], "template_hash": preset['template_hash'],
        "bots": [{k: b[k] for k in ("player_id", "profile_name", "display_name", "side", "overall", "form_delta", "effective_strength", "role", "tier", "stats", "aim_preset", "parameters", "profile_hash", "avatar_path", "avatar_hash", "avatar_kind")} for b in bots],
        "vpk_sha256": vpk_sha,
    }
    for bot, prepared in zip(manifest["bots"], bots):
        if "tactical_abilities" in prepared:
            bot["tactical_abilities"] = dict(prepared["tactical_abilities"])
    if "human_tactical_abilities" in match:
        from ..arena_roles import validate_tactical_abilities
        human_scores = match["human_tactical_abilities"]
        manifest["human_tactical_abilities"] = ({} if match.get("observer") is True and human_scores == {}
            else validate_tactical_abilities(human_scores))
    manifest["manifest_hash"] = _manifest_hash(manifest)
    # Validate all JSON numbers before replacing any active game artifact.
    manifest_payload = json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False).encode()
    nonce = re.sub(r"[^a-fA-F0-9]", "", str(match["nonce"]))[:64]
    _atomic_bytes((cache_root or (save_root() / "botprofiles")) / f"botprofile-{nonce}.vpk", payload)
    active = csgo / "overrides" / MATCH_VPK
    _atomic_bytes(active, payload)
    _atomic_bytes(csgo / "overrides" / "botprofile.manifest.json", manifest_payload)
    if hashlib.sha256(active.read_bytes()).hexdigest() != vpk_sha:
        raise ValueError("活动 VPK 写入后的 SHA-256 校验失败")
    match.update({"schema_version": 2, "difficulty": difficulty, "bots": manifest["bots"]})
    match["bot_profile"] = {"type": profile_type, "nonce": match["nonce"], "count": count, "difficulty": difficulty, "vpk_sha256": vpk_sha, "manifest_hash": manifest["manifest_hash"], "short_hash": manifest["manifest_hash"][:8]}
    match['bot_profile'].update({key: manifest[key] for key in ('difficulty_model','preset_source_hash','template_hash','vpk_file')})
    for side in ("ct", "t"):
        match[side]["players"] = [b for b in manifest["bots"] if b["side"] == side]
    return manifest


def active_vpk_path(csgo: Path) -> Path:
    try:
        data = json.loads((csgo / 'overrides' / 'botprofile.manifest.json').read_text('utf-8-sig'))
        name = data.get('vpk_file', 'botprofile.vpk')
        if name not in ('botprofile.vpk', MATCH_VPK):
            raise ValueError('不支持的活动 VPK 路径')
    except (OSError, ValueError):
        name = MATCH_VPK
    return csgo / 'overrides' / name


def active_manifest(csgo: Path) -> dict:
    path = csgo / "overrides" / "botprofile.manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        filename = data.get('vpk_file', 'botprofile.vpk')
        if filename not in ('botprofile.vpk', MATCH_VPK):
            raise ValueError('不支持的活动 VPK 路径')
        active = csgo / 'overrides' / filename
        bots = data.get("bots") or []
        ids = [bot.get("player_id") for bot in bots]
        names = [bot.get("profile_name") for bot in bots]
        count = 10 if data.get('type') == 'observer_match_10' else 9
        model = data.get("difficulty_model")
        if model and model != 'custom_botprofile_templates_v1':
            if model != improver_presets.MODEL:
                raise ValueError("不支持的 Bot 难度模型")
            preset = improver_presets.preset(data["difficulty"])
            if (data.get("preset_source_hash") != preset["source_hash"]
                    or data.get("template_hash") != preset["template_hash"]):
                raise ValueError("Bot 基础预设来源不一致")
        data["valid"] = (
            data.get('type') in ('career_match_9', 'observer_match_10')
            and active.is_file()
            and hashlib.sha256(active.read_bytes()).hexdigest() == data.get("vpk_sha256")
            and data.get("count") == count
            and len(bots) == count
            and len(set(ids)) == count
            and len(set(names)) == count
            and data.get("manifest_hash") == _manifest_hash(data)
            and all(_avatar_valid(bot) for bot in bots)
        )
        if not data["valid"]:
            data["error"] = "活动 VPK 哈希或选手清单不一致"
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return {"valid": False, "error": "活动 BotProfile 清单不存在或损坏"}


def _avatar_valid(bot: dict) -> bool:
    """Validate the exact safe PNG bound into the match manifest."""
    try:
        path = Path(str(bot.get("avatar_path") or ""))
        payload = path.read_bytes()
        return (
            0 < len(payload) <= 16 * 1024
            and payload.startswith(b"\x89PNG\r\n\x1a\n")
            and hashlib.sha256(payload).hexdigest() == bot.get("avatar_hash")
        )
    except OSError:
        return False
