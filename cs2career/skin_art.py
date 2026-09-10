"""Read-only artwork manifest and bounded, atomic PNG cache.

Never accepts arbitrary client URLs or paths. Missing artwork is a real empty
state, not another item's picture. UI uses local URLs only.
"""
import json
import hashlib
import threading
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from .paths import data_file, save_root

LOCK = threading.Lock()
ITEM_LOCKS = {}


def manifest():
    path = data_file('skin_art.json')
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'items': {}}


def artwork(skin_id):
    row = manifest()['items'].get(skin_id) or {}
    url = row.get('url') or ''
    parsed = urlparse(url)
    approved = ((parsed.hostname == 'raw.githubusercontent.com' and parsed.path.startswith('/ByMykel/counter-strike-image-tracker/')) or
                (parsed.hostname == 'community.akamai.steamstatic.com' and parsed.path.startswith('/economy/image/')))
    if row.get('status') != 'mapped' or parsed.scheme != 'https' or not approved:
        return None
    name = hashlib.sha256(url.encode()).hexdigest()+'.png'
    root = save_root()/'skin_art'
    root.mkdir(exist_ok=True)
    target = root/name
    with LOCK:
        item_lock = ITEM_LOCKS.setdefault(name, threading.Lock())
    with item_lock:
        if target.is_file():
            return target
        try:
            with urlopen(Request(url, headers={'User-Agent': 'CS2Career-art-cache'}), timeout=12) as response:
                if urlparse(response.url).hostname != parsed.hostname:
                    return None
                blob = response.read(4*1024*1024+1)
            if len(blob)>4*1024*1024 or not blob.startswith(b'\x89PNG\r\n\x1a\n'):
                return None
            temp = target.with_suffix('.tmp')
            temp.write_bytes(blob)
            temp.replace(target)
            return target
        except (OSError, ValueError):
            return None
