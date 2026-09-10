# coding=utf-8
"""Generate a self-contained nine-bot profile pack for one career match.

1.5 never copies Bot Improver's player database. The only persistent input is
the sanitised template file shipped with this app.
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
from . import improver_presets

VPK_SIGNATURE = 0x55AA1234
ENTRY_NAME = "botprofile"
ENTRY_EXT = "db"
NO_ARCHIVE = 0x7FFF
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
    lines = [f'{bot["tier"]}+{weapon}+{personality} "{bot["profile_name"]}"']
    lines += [f"    {key} = {value}" for key, value in bot["parameters"].items()]
    lines += [f"    VoicePitch = {90 + crc32(bot['player_id'].encode('ascii')) % 21}", "End", ""]
    return "\n".join(lines)


def prepare_bots(match: dict, difficulty: str) -> list[dict]:
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
            row["profile_hash"] = hashlib.sha256(_profile_block(row).encode()).hexdigest()
            if not _avatar_valid(row):
                raise ValueError(f"{pid} 没有通过校验的本地安全头像")
            rows.append(row)
    ids, names = [r["player_id"] for r in rows], [r["profile_name"] for r in rows]
    if len(rows) != 9:
        raise ValueError(f"本场必须恰好有 9 个 Bot，当前为 {len(rows)} 个")
    if len(set(ids)) != 9 or len(set(names)) != 9:
        raise ValueError("本场 Bot 的 player_id 或 profile_name 重复")
    return rows


def _template_text(difficulty: str = 'Medium') -> str:
    text = improver_presets.preset(difficulty)['text']
    required = ("Default", "RankRifler", "RankDuelist", "RankOthers", "ProSlow", "ProSteady", "ProFast", "ProPrecise", "ProTop", "RiflePro", "SniperPro", "Rusher", "Camper", "RiflePersonality", "SniperPersonality", "RusherPersonality", "CamperPersonality")
    missing = [n for n in required if not re.search(rf"(?m)^(?:Template )?{re.escape(n)}\b", text)]
    if missing:
        raise ValueError("BotProfile 模板缺失：" + ", ".join(missing))
    return text.rstrip() + "\n\n"


def vpk_bytes(db_text: str) -> bytes:
    data = db_text.encode("utf-8")
    tree = (f"{ENTRY_EXT}\0".encode() + b" \0" + f"{ENTRY_NAME}\0".encode()
            + struct.pack("<IHHIIH", crc32(data), 0, NO_ARCHIVE, 0, len(data), 0xFFFF) + b"\0\0\0")
    header = struct.pack("<IIIIIII", VPK_SIGNATURE, 2, len(tree), len(data), 0, 48, 0)
    body = header + tree + data
    return body + hashlib.md5(tree).digest() + hashlib.md5(b"").digest() + hashlib.md5(body).digest()


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
    for bot in sorted(manifest.get("bots") or [], key=lambda row: row["player_id"]):
        lines.append(
            "bot=" + "|".join(str(bot[key]) for key in (
                "player_id", "profile_name", "side", "profile_hash", "avatar_hash"
            ))
        )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def generate_match_vpk(csgo: Path, match: dict, difficulty: str, cache_root: Path | None = None) -> dict:
    bots = prepare_bots(match, difficulty)
    preset = improver_presets.preset(difficulty)
    db_text = _template_text(difficulty) + "".join(_profile_block(bot) for bot in bots)
    if PROFILE_RE.findall(db_text) != [b["profile_name"] for b in bots]:
        raise ValueError("生成后的 BotProfile 清单与请求不一致")
    payload, vpk_sha = vpk_bytes(db_text), hashlib.sha256(vpk_bytes(db_text)).hexdigest()
    manifest = {
        "schema_version": 2, "type": "career_match_9", "nonce": match["nonce"], "difficulty": difficulty, "count": 9,
        "difficulty_model": improver_presets.MODEL,
        "preset_source_hash": preset['source_hash'], "template_hash": preset['template_hash'],
        "bots": [{k: b[k] for k in ("player_id", "profile_name", "display_name", "side", "overall", "form_delta", "effective_strength", "role", "tier", "stats", "aim_preset", "parameters", "profile_hash", "avatar_path", "avatar_hash", "avatar_kind")} for b in bots],
        "vpk_sha256": vpk_sha,
    }
    manifest["manifest_hash"] = _manifest_hash(manifest)
    # Validate all JSON numbers before replacing any active game artifact.
    manifest_payload = json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False).encode()
    nonce = re.sub(r"[^a-fA-F0-9]", "", str(match["nonce"]))[:64]
    _atomic_bytes((cache_root or (save_root() / "botprofiles")) / f"botprofile-{nonce}.vpk", payload)
    active = csgo / "overrides" / "botprofile.vpk"
    _atomic_bytes(active, payload)
    _atomic_bytes(csgo / "overrides" / "botprofile.manifest.json", manifest_payload)
    if hashlib.sha256(active.read_bytes()).hexdigest() != vpk_sha:
        raise ValueError("活动 VPK 写入后的 SHA-256 校验失败")
    match.update({"schema_version": 2, "difficulty": difficulty, "bots": manifest["bots"]})
    match["bot_profile"] = {"type": "career_match_9", "nonce": match["nonce"], "count": 9, "difficulty": difficulty, "vpk_sha256": vpk_sha, "manifest_hash": manifest["manifest_hash"], "short_hash": manifest["manifest_hash"][:8]}
    match['bot_profile'].update({key: manifest[key] for key in ('difficulty_model','preset_source_hash','template_hash')})
    for side in ("ct", "t"):
        match[side]["players"] = [b for b in manifest["bots"] if b["side"] == side]
    return manifest


def active_manifest(csgo: Path) -> dict:
    path, active = csgo / "overrides" / "botprofile.manifest.json", csgo / "overrides" / "botprofile.vpk"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        bots = data.get("bots") or []
        ids = [bot.get("player_id") for bot in bots]
        names = [bot.get("profile_name") for bot in bots]
        model = data.get("difficulty_model")
        if model:
            if model != improver_presets.MODEL:
                raise ValueError("不支持的 Bot 难度模型")
            preset = improver_presets.preset(data["difficulty"])
            if (data.get("preset_source_hash") != preset["source_hash"]
                    or data.get("template_hash") != preset["template_hash"]):
                raise ValueError("Bot 基础预设来源不一致")
        data["valid"] = (
            active.is_file()
            and hashlib.sha256(active.read_bytes()).hexdigest() == data.get("vpk_sha256")
            and data.get("count") == 9
            and len(bots) == 9
            and len(set(ids)) == 9
            and len(set(names)) == 9
            and data.get("manifest_hash") == _manifest_hash(data)
            and all(_avatar_valid(bot) for bot in bots)
        )
        if not data["valid"]:
            data["error"] = "活动 VPK 哈希或 9 人清单不一致"
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
