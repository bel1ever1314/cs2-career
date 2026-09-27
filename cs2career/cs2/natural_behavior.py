# coding=utf-8
"""Small, auditable pro-demo movement preset for career bots.

This is deliberately not a prerecorded route player.  It adjusts live bot
navigation so CareerMatch, BotBuy, BotHider and takeover accounting retain
ownership of their existing responsibilities.  Only aggregate demo metrics
are bundled; the user's original demos and extracted tracks stay outside the
application.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import os
from functools import lru_cache

from ..paths import data_file
from .motion_clips import motion_clip_pack

MODES = ("classic", "natural")
SUPPORTED_MAPS = ("de_dust2",)
PROFILE_FILE = "natural_behavior/de_dust2.json"
BEHAVIOR_FILE = "natural_behavior/de_dust2_nodes.json"
CORNER_FILE = "natural_behavior/de_dust2_corners.json"

# Restore the exact Bot Improver defaults after a Natural match.  Without
# this reset, Source cvars survive map changes for the lifetime of the server.
CLASSIC_CVARS = {
    "nav_smooth_spring_yaw_rotation_speed": 999999.0,
    "nav_smooth_spring_yaw_threshold": 359.0,
    "npcsolve_path_lookahead_const": 20.0,
    "npcsolve_path_lookahead_dist": 8000.0,
    "bot_defense_rush_chance": 0.0,
}


@lru_cache(maxsize=1)
def profile() -> dict:
    raw = data_file(PROFILE_FILE).read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if data.get("schema_version") != 1 or data.get("supported_maps") != list(SUPPORTED_MAPS):
        raise ValueError("自然行为参数包版本或地图声明不受支持")
    cvars = data.get("runtime_cvars") or {}
    if set(cvars) != set(CLASSIC_CVARS):
        raise ValueError("自然行为参数包包含未知或缺失的运行参数")
    for key, value in cvars.items():
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
            raise ValueError(f"自然行为参数无效：{key}")
    data["sha256"] = hashlib.sha256(raw).hexdigest()
    return data


@lru_cache(maxsize=1)
def behavior_pack() -> tuple[Path, dict, bytes]:
    """Load and validate the data-only professional Dust2 node pack."""
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    override = os.environ.get("CS2CAREER_NATURAL_ROUTES")
    adjacent = root / "natural_routes" / "de_dust2.json"
    path = Path(override) if override else adjacent if adjacent.is_file() else data_file(BEHAVIOR_FILE)
    raw = path.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("自然行为节点包超过 2 MB")
    pack = json.loads(raw.decode("utf-8"))
    if pack.get("schema_version") != 3 or pack.get("map") != "de_dust2":
        raise ValueError("自然行为节点包版本或地图不匹配")
    nodes, edges, formations = pack.get("nodes"), pack.get("edges"), pack.get("formations")
    if not isinstance(nodes, list) or not nodes or len(nodes) > 800:
        raise ValueError("自然行为节点数量无效")
    if not isinstance(edges, list) or not isinstance(formations, list):
        raise ValueError("自然行为节点包缺少路径边或阵型")
    ids = [str(node.get("id") or "") for node in nodes if isinstance(node, dict)]
    if len(ids) != len(nodes) or len(set(ids)) != len(ids) or any(not value for value in ids):
        raise ValueError("自然行为节点 ID 无效或重复")
    references = set(ids)
    positions: dict[str, tuple[float, float, float]] = {}
    for node in nodes:
        position = node.get("position")
        if (node.get("side") not in {"ct", "t"} or node.get("territory") not in {"ct_home", "contested", "t_home"}
                or not isinstance(position, list) or len(position) != 3
                or any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in position)
                or not isinstance(node.get("radius"), (int, float)) or not 40 <= float(node["radius"]) <= 240):
            raise ValueError(f"自然行为节点内容无效：{node.get('id')}")
        positions[node["id"]] = tuple(float(value) for value in position)
        if (node.get("zone") not in {"a", "b", "mid", "spawn", "unknown"}
                or not isinstance(node.get("safe_radius"), (int, float))
                or not 16 <= float(node["safe_radius"]) <= 48
                or not isinstance(node.get("cover_group"), str) or not node["cover_group"]):
            raise ValueError(f"自然行为节点战术属性无效：{node.get('id')}")
        anchors = node.get("aim_lanes") or []
        if len(anchors) > 6 or len(node.get("peek_primitives") or []) > 2:
            raise ValueError(f"自然行为节点动作数量无效：{node.get('id')}")
        for anchor in anchors:
            target = anchor.get("target")
            if (not isinstance(anchor.get("lane"), str) or not anchor["lane"]
                    or anchor.get("confidence") not in {"high", "medium"}
                    or not isinstance(target, list) or len(target) != 3
                    or any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in target)):
                raise ValueError(f"自然行为预瞄锚点无效：{node.get('id')}")
        if any(not isinstance(row.get("lane"), str) or not row["lane"]
               for row in node.get("exposure_lanes") or []):
            raise ValueError(f"自然行为暴露通道无效：{node.get('id')}")
        lanes = {anchor["lane"] for anchor in anchors}
        if any(peek.get("lane") not in lanes for peek in node.get("peek_primitives") or []):
            raise ValueError(f"自然行为 peek 未绑定有效通道：{node.get('id')}")
        if any(not isinstance(peek.get("offset"), list) or len(peek["offset"]) != 2
               or math.hypot(float(peek["offset"][0]), float(peek["offset"][1])) > 48
               for peek in node.get("peek_primitives") or []):
            raise ValueError(f"自然行为 peek 超出安全微调范围：{node.get('id')}")
    if any(edge.get("from") not in references or edge.get("to") not in references for edge in edges):
        raise ValueError("自然行为路径引用了不存在的节点")
    for edge in edges:
        start, end = positions[edge["from"]], positions[edge["to"]]
        if math.dist(start, end) > 280:
            raise ValueError("自然行为路径包含不可解释的跨区边")
    if any(any(node_id not in references for node_id in formation.get("node_ids", [])) for formation in formations):
        raise ValueError("自然行为阵型引用了不存在的节点")
    if any(formation.get("side") not in {"ct", "t"} or not 4 <= len(formation.get("node_ids", [])) <= 5
           for formation in formations):
        raise ValueError("自然行为阵型人数或阵营无效")
    if not any(node.get("aim_lanes") for node in nodes):
        raise ValueError("自然行为节点包没有通过证据校验的威胁通道")
    policy, coverage = pack.get("policy") or {}, pack.get("coverage_rules") or {}
    if (not 650 <= int(policy.get("minimum_hold_ms", 0)) <= 2500
            or not 16 <= float(policy.get("safe_micro_adjust_units", 0)) <= 48
            or not 10000 <= int(policy.get("opening_max_ms", 0)) <= 45000
            or not 45000 <= int(policy.get("late_after_ms", 0)) <= 105000
            or not 250 <= int(policy.get("strategic_alert_delay_ms", 0)) <= 2500
            or not 1000 <= int(policy.get("strategic_memory_ms", 0)) <= 6000
            or not 1200 <= int(policy.get("task_stall_ms", 0)) <= 6000
            or not 8 <= float(policy.get("arrival_distance", 0)) <= 24
            or not 12 <= float(policy.get("arrival_speed", 0)) <= 60
            or not 60 <= int(policy.get("arrival_stable_ms", 0)) <= 350
            or not 2 <= int(coverage.get("cross_zone_enemy_count", 0)) <= 5):
        raise ValueError("自然行为团队策略参数无效")
    return path.resolve(), pack, raw


def configure_match(match: dict, requested: str) -> dict:
    """Bind a requested setting to the actual map-specific behavior."""
    requested = requested if requested in MODES else "classic"
    map_code = str(match.get("map") or "").lower()
    active = "natural" if requested == "natural" and map_code in SUPPORTED_MAPS else "classic"
    info = {
        "requested": requested,
        "active": active,
        "map": map_code,
        "supported": map_code in SUPPORTED_MAPS,
        "profile_id": "",
        "profile_hash": "",
    }
    if active == "natural":
        data = profile()
        info.update(profile_id=data["id"], profile_hash=data["sha256"])
        route, pack, raw = behavior_pack()
        info.update(route_path=str(route), route_hash=hashlib.sha256(raw).hexdigest(),
                    route_schema=3, route_count=len(pack["nodes"]),
                    anchor_count=sum(len(node.get("aim_lanes") or []) for node in pack["nodes"]),
                    formation_count=len(pack["formations"]), route_scope="沙二双方阶段、任务、辅助感知、原生寻路与到位后职业动作")
        corner_path, corners, corner_raw = corner_pack()
        info.update(corner_path=str(corner_path), corner_hash=hashlib.sha256(corner_raw).hexdigest(),
                    corner_schema=1, corner_count=len(corners["actions"]),
                    corner_scope="B上层洞内柱子与B洞出口：按来路匹配成套横移、预瞄和退回动作")
        clip_path, clips, clip_raw = motion_clip_pack()
        info.update(clip_path=str(clip_path), clip_hash=hashlib.sha256(clip_raw).hexdigest(),
                    clip_schema=1, clip_count=len(clips['clips']),
                    clip_scope="连续短动作试验：CT中门跳跃、双方B洞和中路；原位匹配，实时物理，可中断",
                    corner_scope="旧两帧动作仅兼容旧请求；本场由连续动作层替代")
    elif requested == "natural":
        info["fallback_reason"] = "自然行为目前只支持 de_dust2，本场使用原版增强行为"
    match["movement_style"] = info
    return info


@lru_cache(maxsize=1)
def corner_pack() -> tuple[Path, dict, bytes]:
    """Data-only extension; an adjacent file can customize the two-site pilot."""
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    adjacent = root / "natural_routes" / "de_dust2_corners.json"
    path = adjacent if adjacent.is_file() else data_file(CORNER_FILE)
    raw = path.read_bytes()
    if len(raw) > 512 * 1024:
        raise ValueError("B洞动作包超过512 KB")
    pack = json.loads(raw)
    actions = pack.get("actions")
    if (pack.get("schema_version") != 1 or pack.get("map") != "de_dust2"
            or not isinstance(actions, list) or not 1 <= len(actions) <= 128):
        raise ValueError("B洞动作包版本、地图或动作数量不正确")
    return path.resolve(), pack, raw


def cfg_lines(match: dict) -> list[str]:
    info = match.get("movement_style") or {}
    active = info.get("active") == "natural" and str(match.get("map") or "").lower() in SUPPORTED_MAPS
    values = profile()["runtime_cvars"] if active else CLASSIC_CVARS
    lines = [f"// Career movement style: {'natural_dust2' if active else 'classic'}"]
    for key in CLASSIC_CVARS:
        lines.append(f"{key} {float(values[key]):g}")
    return lines
