# coding=utf-8
"""Safe, deterministic loader for user extension packs.

Packs are data, never Python.  A bad pack is isolated and reported in the
desktop UI instead of preventing the game from starting.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..paths import extension_root

PACK_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
KINDS = {"stories", "skins", "events", "teams", "eras"}


@dataclass
class Pack:
    id: str
    name: str
    version: str
    path: Path
    load_order: int = 100
    kinds: list[str] = field(default_factory=list)
    enabled: bool = True
    status: str = "ready"
    errors: list[str] = field(default_factory=list)
    payloads: dict[str, list[dict]] = field(default_factory=dict)

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "path": str(self.path),
            "load_order": self.load_order,
            "kinds": self.kinds,
            "enabled": self.enabled,
            "status": self.status,
            "errors": self.errors,
        }


class PackRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or extension_root()
        self.packs: list[Pack] = []
        self.errors: list[str] = []
        self.scan()

    def scan(self) -> "PackRegistry":
        self.packs = []
        self.errors = []
        seen: set[str] = set()
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in sorted(self.root.iterdir(), key=lambda p: p.name.casefold()):
            if not folder.is_dir() or folder.name.startswith(("_", ".")):
                continue
            pack = self._load_pack(folder)
            if pack.id in seen:
                pack.errors.append(f"扩展包 id 重复：{pack.id}")
                pack.status = "rejected"
            seen.add(pack.id)
            self.packs.append(pack)
        self.packs.sort(key=lambda p: (p.load_order, p.id))
        return self

    def _load_pack(self, folder: Path) -> Pack:
        manifest = folder / "pack.json"
        try:
            raw = json.loads(manifest.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return Pack(folder.name, folder.name, "?", folder, status="rejected", errors=["缺少 pack.json"])
        except (OSError, ValueError) as exc:
            return Pack(folder.name, folder.name, "?", folder, status="rejected", errors=[f"pack.json 无法读取：{exc}"])
        if not isinstance(raw, dict):
            return Pack(folder.name, folder.name, '?', folder, status='rejected', errors=['pack.json 顶层必须是对象'])
        if not isinstance(raw.get('load_order',100),int) or not isinstance(raw.get('schema_version'),int) or not isinstance(raw.get('types',[]),list):
            return Pack(folder.name,folder.name,'?',folder,status='rejected',errors=['schema_version/load_order 必须为整数，types 必须为数组'])
        pack = Pack(
            id=str(raw.get("id") or folder.name),
            name=str(raw.get("name") or folder.name),
            version=str(raw.get("version") or "0.0.0"),
            path=folder,
            load_order=int(raw.get("load_order") or 100),
            kinds=[str(x) for x in (raw.get("types") or [])],
            enabled=bool(raw.get("enabled", True)),
        )
        if int(raw.get("schema_version") or 0) != 1:
            pack.errors.append("只支持 pack.json schema_version 1")
        if not PACK_ID.match(pack.id):
            pack.errors.append("id 只能使用 3-64 位小写字母、数字、点、横线或下划线")
        unknown = [kind for kind in pack.kinds if kind not in KINDS]
        if unknown:
            pack.errors.append("未知扩展类型：" + "、".join(unknown))
        if not pack.enabled:
            pack.status = "disabled"
            return pack
        for kind in pack.kinds:
            pack.payloads[kind] = self._read_payloads(pack, kind)
        if pack.errors:
            pack.status = "rejected"
            pack.payloads = {}
        return pack

    @staticmethod
    def _read_payloads(pack: Pack, kind: str) -> list[dict]:
        folder = pack.path / kind
        if not folder.is_dir():
            pack.errors.append(f"声明了 {kind}，但缺少 {kind}/ 目录")
            return []
        out: list[dict] = []
        for path in sorted(folder.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                pack.errors.append(f"{path.name} 无法读取：{exc}")
                continue
            if not isinstance(raw, dict):
                pack.errors.append(f"{path.name} 顶层必须是对象")
                continue
            raw = dict(raw)
            for key in ('stories','skins','cases','events','teams'):
                if key in raw and (not isinstance(raw[key],list) or any(not isinstance(row,dict) for row in raw[key])):
                    pack.errors.append(f'{path.name}: {key} 必须是对象数组')
            stories = raw.get('stories', [])
            if kind == 'stories' and isinstance(stories, list) and any(not isinstance(row.get('text',''),str) for row in stories if isinstance(row,dict)):
                pack.errors.append(f'{path.name}: 剧情 text 必须是文本')
            if kind == 'stories' and isinstance(stories,list):
                for row in stories:
                    if not isinstance(row,dict): continue
                    if any(not isinstance(row.get(k,''),str) for k in ('id','when','title')) or not row.get('id') or not row.get('when'):
                        pack.errors.append(f'{path.name}: 剧情 id/when 必须是非空文本，title 必须是文本')
            raw["_pack_id"] = pack.id
            raw["_source"] = str(path)
            out.append(raw)
        return out

    def payloads(self, kind: str) -> list[dict]:
        rows: list[dict] = []
        for pack in self.packs:
            if pack.status == "ready":
                rows.extend(pack.payloads.get(kind) or [])
        return rows

    def public(self) -> dict:
        ready = sum(p.status == "ready" for p in self.packs)
        return {"root": str(self.root), "ready": ready, "packs": [p.public() for p in self.packs]}


_REGISTRY: PackRegistry | None = None


def get_registry() -> PackRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = PackRegistry()
    return _REGISTRY


def reload_registry() -> PackRegistry:
    global _REGISTRY
    _REGISTRY = PackRegistry()
    return _REGISTRY
