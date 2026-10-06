"""Bounded, map-specific playbooks, independent of career saves and CS2.

Editing this library never installs files or touches a running game. The launcher
can publish its validated snapshot to a verified, closed-game current session.
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
import unicodedata
from pathlib import Path

from .paths import data_file, save_file

SCHEMA_VERSION = 1
MAP = "de_dust2"
SUPPORTED_MAPS = ("de_dust2", "de_mirage", "de_inferno", "de_nuke", "de_ancient",
                  "de_anubis", "de_overpass", "de_train", "de_vertigo", "de_cache")
MAX_BYTES = 256 * 1024
MAX_TACTICS = 20
MAX_STEPS = 12
MAX_JSON_DEPTH = 16
ASSIGNMENTS = ("roster", "ability")
DUTIES = ("auto", "awp", "entry", "lurk", "rifle", "igl")
MOVEMENTS = ("run", "walk")
MAP_META = {"image": "/tactical_maps/de_dust2.png", "pos_x": -2476,
            "pos_y": 3239, "scale": 4.4, "width": 1024, "height": 1024}
RUNTIME_NOTE = ("地图战术：分路、到点等待与箭头观察；交火优先原生 AI，下包后 T 守包、CT 回防。"
                "仅正式准备阶段选战术，不控制真人。保存后 CS2 关闭时自动同步当前对局；"
                "运行时仅保存，退出后点击同步，不需重新准备或重置比赛。")
_ID = re.compile(r"[a-z0-9_-]{1,32}\Z", re.ASCII)
_LOCK = threading.RLock()


def validate_map_code(value) -> str:
    if not isinstance(value, str) or value not in SUPPORTED_MAPS:
        raise ValueError("不支持的战术地图")
    return value


def canonical_map(value) -> str:
    if not isinstance(value, str):
        raise ValueError("不支持的战术地图")
    return validate_map_code(value if value.startswith("de_") else f"de_{value}")


def _map_registry() -> dict:
    with data_file("tactical_maps.json").open("rb") as source:
        registry = decode_json(source.read(MAX_BYTES + 1))
    if not isinstance(registry, dict) or set(registry) not in ({"schema_version", "maps"}, {"schema_version", "source", "maps"}):
        raise ValueError("地图目录字段错误")
    if type(registry["schema_version"]) is not int or registry["schema_version"] != SCHEMA_VERSION:
        raise ValueError("地图目录版本错误")
    if not isinstance(registry["maps"], dict) or set(registry["maps"]) != set(SUPPORTED_MAPS):
        raise ValueError("地图目录缺少支持的地图或包含未知地图")
    return registry["maps"]


def map_metadata(map_code: str = MAP) -> dict:
    map_code = validate_map_code(map_code)
    meta = _map_registry()[map_code]
    if not isinstance(meta, dict):
        raise ValueError("地图投影元数据错误")
    for key in ("pos_x", "pos_y", "scale", "width", "height"):
        _number(meta.get(key), "地图投影参数")
    if any(meta[key] <= 0 for key in ("scale", "width", "height")):
        raise ValueError("地图投影尺寸必须为正数")
    # The registry is bundled read-only data; callers get independent metadata.
    return json.loads(json.dumps(meta, ensure_ascii=False, allow_nan=False))


def available_maps() -> list[dict]:
    registry = _map_registry()
    return [{"map": code, "name": registry[code]["name"]} for code in SUPPORTED_MAPS]


def library_path(map_code: str = MAP) -> Path:
    # Resolve on every operation so isolated previews/tests use their own root.
    map_code = validate_map_code(map_code)
    return save_file("tactics.json" if map_code == MAP else f"tactics_{map_code}.json")


def _keys(value, required: set[str], label: str, optional: set[str] | None = None) -> dict:
    allowed = required | (optional or set())
    if not isinstance(value, dict) or not required <= set(value) <= allowed:
        raise ValueError(f"{label}字段错误；仅允许：{', '.join(sorted(allowed))}")
    return value


def _number(value, label: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{label}必须是有限数值")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label}必须是有限数值") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label}必须是有限数值")
    return number


def _pair(value, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label}必须是两个坐标")
    return [_number(value[0], label), _number(value[1], label)]


def _validate_position(value, label: str, meta: dict) -> list[float]:
    x, y = _pair(value, label)
    x0, y0, scale = meta["pos_x"], meta["pos_y"], meta["scale"]
    if not x0 <= x <= x0 + meta["width"] * scale or not y0 - meta["height"] * scale <= y <= y0:
        raise ValueError(f"{label}超出{meta.get('name', '地图')}雷达范围")
    return [x, y]


def validate_position(value, label: str = "坐标", map_code: str = MAP) -> list[float]:
    return _validate_position(value, label, map_metadata(map_code))


def world_to_pixel(position, map_code: str = MAP) -> list[float]:
    meta = map_metadata(map_code)
    x, y = _validate_position(position, "坐标", meta)
    return [(x - meta["pos_x"]) / meta["scale"], (meta["pos_y"] - y) / meta["scale"]]


def pixel_to_world(position, map_code: str = MAP) -> list[float]:
    meta = map_metadata(map_code)
    x, y = _pair(position, "雷达坐标")
    if not 0 <= x <= meta["width"] or not 0 <= y <= meta["height"]:
        raise ValueError("雷达坐标超出图片范围")
    return [meta["pos_x"] + x * meta["scale"], meta["pos_y"] - y * meta["scale"]]


def validate_id(value) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("战术 ID 必须为 1–32 个小写英文字母、数字、下划线或短横线")
    return value


def validate_tactic(value, map_code: str = MAP) -> dict:
    meta = map_metadata(map_code)
    row = _keys(value, {"id", "name", "side", "slots"}, "战术", {"assignment", "human_slot"})
    assignment = row.get("assignment", "roster")
    if assignment not in ASSIGNMENTS:
        raise ValueError("战术分配方式只能是 roster 或 ability")
    human_slot = row.get("human_slot", 1)
    if type(human_slot) is not int or human_slot not in range(1, 6):
        raise ValueError("真人槽位必须是整数 1–5")
    if assignment == "roster" and human_slot != 1:
        raise ValueError("名单分配的真人槽位必须为 1")
    ident = validate_id(row["id"])
    name = row["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > 40 or any(unicodedata.category(ch).startswith("C") for ch in name):
        raise ValueError("战术名称须为 1–40 个可见字符")
    if row["side"] not in ("t", "ct"):
        raise ValueError("战术阵营只能是 t 或 ct")
    if not isinstance(row["slots"], list) or len(row["slots"]) != 5:
        raise ValueError("战术必须恰好包含 1–5 号五个槽位")
    slots, seen = [], set()
    for slot in row["slots"]:
        slot = _keys(slot, {"slot", "steps"}, "槽位", {"duty", "finish"})
        finish = slot.get("finish", "auto")
        if finish not in ("auto", "hold", "native"):
            raise ValueError("路线结束方式只能是 auto、hold 或 native")
        duty = slot.get("duty", "auto")
        if duty not in DUTIES:
            raise ValueError("槽位职责只能是 auto、awp、entry、lurk、rifle 或 igl")
        index = slot["slot"]
        if type(index) is not int or index not in range(1, 6) or index in seen:
            raise ValueError("槽位须为不重复的整数 1–5")
        seen.add(index)
        if not isinstance(slot["steps"], list) or len(slot["steps"]) > MAX_STEPS:
            raise ValueError(f"每个槽位最多 {MAX_STEPS} 步，可为空")
        steps = []
        for step in slot["steps"]:
            step = _keys(step, {"position", "level", "wait", "look_at"}, "步骤", {"movement"})
            movement = step.get("movement", "run")
            if movement not in MOVEMENTS:
                raise ValueError("步骤移动方式只能是 run 或 walk")
            position = _validate_position(step["position"], "坐标", meta)
            if step["level"] not in ("auto", "upper", "lower"):
                raise ValueError("步骤层级只能是 auto、upper 或 lower")
            wait = _number(step["wait"], "等待秒数")
            if not 0 <= wait <= 30:
                raise ValueError("等待秒数须在 0–30 之间")
            look_at = None if step["look_at"] is None else _validate_position(step["look_at"], "观察方向坐标", meta)
            clean_step = {"position": position, "level": step["level"], "wait": wait, "look_at": look_at}
            # Missing movement means run; keep legacy libraries' exact shape.
            if "movement" in step:
                clean_step["movement"] = movement
            steps.append(clean_step)
        clean_slot = {"slot": index, "steps": steps}
        if "duty" in slot:
            clean_slot["duty"] = duty
        if "finish" in slot:
            clean_slot["finish"] = finish
        slots.append(clean_slot)
    clean = {"id": ident, "name": name.strip(), "side": row["side"], "slots": sorted(slots, key=lambda s: s["slot"])}
    if "assignment" in row:
        clean["assignment"] = assignment
    if "human_slot" in row:
        clean["human_slot"] = human_slot
    return clean


def empty_library(map_code: str = MAP) -> dict:
    return {"schema_version": SCHEMA_VERSION, "map": validate_map_code(map_code), "tactics": []}


def encode_library(library: dict) -> bytes:
    blob = json.dumps(library, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(blob) > MAX_BYTES:
        raise ValueError("战术库超过 256 KiB 大小限制")
    return blob


def validate_library(value, map_code: str | None = None) -> dict:
    value = _keys(value, {"schema_version", "map", "tactics"}, "战术库")
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        raise ValueError("仅支持 schema_version=1 的战术库")
    package_map = validate_map_code(value["map"])
    if map_code is not None and validate_map_code(map_code) != package_map:
        raise ValueError("战术包地图与当前所选地图不一致；未写入任何条目")
    if not isinstance(value["tactics"], list) or len(value["tactics"]) > MAX_TACTICS:
        raise ValueError(f"战术库最多 {MAX_TACTICS} 个战术")
    rows, seen = [], set()
    for row in value["tactics"]:
        clean = validate_tactic(row, package_map)
        if clean["id"] in seen:
            raise ValueError(f"导入包中战术 ID 重复：{clean['id']}；未写入任何条目")
        seen.add(clean["id"])
        rows.append(clean)
    clean = {"schema_version": SCHEMA_VERSION, "map": package_map, "tactics": rows}
    encode_library(clean)
    return clean


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON 字段重复：{key}")
        result[key] = value
    return result


def decode_json(blob: bytes):
    if len(blob) > MAX_BYTES:
        raise ValueError("战术数据超过 256 KiB 大小限制")
    try:
        value = json.loads(blob.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                           parse_constant=lambda text: (_ for _ in ()).throw(ValueError(f"非法 JSON 数值：{text}")))
        pending = [(value, 0)]
        while pending:
            current, depth = pending.pop()
            if depth > MAX_JSON_DEPTH:
                raise ValueError("JSON 嵌套层级过深")
            if isinstance(current, dict):
                pending.extend((child, depth + 1) for child in current.values())
            elif isinstance(current, list):
                pending.extend((child, depth + 1) for child in current)
        return value
    except (UnicodeError, RecursionError, ValueError) as exc:
        raise ValueError(f"战术数据不是有效 JSON：{exc}") from exc


def load_library(map_code: str = MAP) -> dict:
    map_code = validate_map_code(map_code)
    with _LOCK:
        path = library_path(map_code)
        from .storage.transaction import read_bytes
        try:
            blob = read_bytes(path, max_bytes=MAX_BYTES + 1)
        except FileNotFoundError:
            if map_code != MAP:
                return empty_library(map_code)
            path = data_file("tactical_playbook.json")  # Dust2 examples stay read-only.
            if not path.exists():
                return empty_library(map_code)
            blob = path.read_bytes()
        return validate_library(decode_json(blob[:MAX_BYTES + 1]), map_code)


def write_library(path: Path, library: dict, *, before_replace=None) -> None:
    """Atomically write validated data; arbitrary destinations are never HTTP input."""
    blob = encode_library(validate_library(library))
    path = Path(path)
    # The application-owned library shares the career commit. Runtime exports
    # use their own atomic replacement (and optional live-session guard).
    if path.absolute() == library_path(library['map']).absolute() and before_replace is None:
        from .storage.transaction import save
        save(path, lambda: blob)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    pending = Path(temporary)
    try:
        with os.fdopen(handle, "wb") as target:
            target.write(blob)
            target.flush()
            os.fsync(target.fileno())
        if before_replace is not None:
            before_replace()
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def public_library(map_code: str = MAP) -> dict:
    return {**load_library(map_code), "map_meta": map_metadata(map_code), "available_maps": available_maps(), "runtime_note": RUNTIME_NOTE,
            "slot_labels": ["你 · 手动操作", "队友1", "队友2", "队友3", "队友4"]}


def _merge(rows: list[dict], map_code: str = MAP) -> tuple[dict, list[str]]:
    current = load_library(map_code)
    lookup = {row["id"]: index for index, row in enumerate(current["tactics"])}
    overwritten = []
    for row in rows:
        ident = row["id"]
        if ident in lookup:
            overwritten.append(ident)
            current["tactics"][lookup[ident]] = row
        else:
            lookup[ident] = len(current["tactics"])
            current["tactics"].append(row)
    current = validate_library(current)  # Reject the complete merge, never truncate.
    write_library(library_path(map_code), current)
    return current, overwritten


def save_tactic(value, map_code: str = MAP) -> dict:
    row = validate_tactic(value, map_code)
    with _LOCK:
        library, overwritten = _merge([row], map_code)
    return {"ok": True, **library, "tactic": row, "overwritten_ids": overwritten,
            "msg": "已覆盖同 ID 战术：" + row["id"] if overwritten else "战术已保存到独立库；游戏文件未修改。"}


def delete_tactic(ident, map_code: str = MAP) -> dict:
    map_code = validate_map_code(map_code)
    ident = validate_id(ident)
    with _LOCK:
        library = load_library(map_code)
        kept = [row for row in library["tactics"] if row["id"] != ident]
        if len(kept) == len(library["tactics"]):
            raise ValueError("战术不存在；未删除其他条目")
        library["tactics"] = kept
        write_library(library_path(map_code), library)
    return {"ok": True, **library, "deleted_id": ident, "msg": "战术已从独立库删除；游戏文件未修改。"}


def import_tactics(value, map_code: str | None = None) -> dict:
    if map_code is not None:
        map_code = validate_map_code(map_code)
    if isinstance(value, dict) and set(value) == {"map", "tactic"}:
        package_map = validate_map_code(value["map"])
        if map_code is not None and package_map != map_code:
            raise ValueError("战术包地图与当前所选地图不一致；未写入任何条目")
        map_code = package_map
        rows = [validate_tactic(value["tactic"], map_code)]
    elif isinstance(value, dict) and set(value) == {"tactic"}:
        map_code = map_code or MAP
        rows = [validate_tactic(value["tactic"], map_code)]
    elif isinstance(value, dict) and {"id", "name", "side", "slots"} <= set(value) <= {"id", "name", "side", "slots", "assignment", "human_slot"}:
        map_code = map_code or MAP
        rows = [validate_tactic(value, map_code)]
    else:
        package = validate_library(value, map_code)
        map_code = package["map"]
        rows = package["tactics"]
    with _LOCK:
        library, overwritten = _merge(rows, map_code)
    msg = f"已完整导入 {len(rows)} 个战术；游戏文件未修改。"
    if overwritten:
        msg += " 已覆盖同 ID 条目：" + ", ".join(overwritten)
    return {"ok": True, **library, "imported_count": len(rows), "overwritten_ids": overwritten, "msg": msg}
