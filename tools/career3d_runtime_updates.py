"""Explicit, read-only checks for Bot Improver's official stable release.

No check runs on import or during installation. GitHub's latest-release endpoint
excludes drafts and prereleases; we also check the response before displaying it.
Reference: https://docs.github.com/en/rest/releases/releases#get-the-latest-release
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from tools.career3d_runtime_compat import load_runtime_manifest


LATEST_API = 'https://api.github.com/repos/ed0ard/CS2-Bot-Improver/releases/latest'
RELEASES_URL = 'https://github.com/ed0ard/CS2-Bot-Improver/releases'
REQUEST_TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 256 * 1024
STEAM_NEWS_API = ('https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/'
                  '?appid=730&count=10&maxlength=0&feeds=steam_community_announcements')


def _stable_version(raw: object) -> tuple[int, ...] | None:
    if not isinstance(raw, str) or len(raw) > 80:
        return None
    match = re.fullmatch(r'[vV]?(\d+(?:\.\d+){1,4})(?:\+[a-zA-Z0-9.-]+)?', raw.strip())
    if not match:
        return None
    parts = tuple(int(part) for part in match.group(1).split('.'))
    return parts + (0,) * (5 - len(parts))


def _local_version() -> str:
    for component in load_runtime_manifest()['components']:
        if component['name'] == 'CS2 Bot Improver':
            return component['version']
    raise ValueError('missing local Bot Improver version')


def _release_url(raw: object) -> str:
    if not isinstance(raw, str) or len(raw) > 1024:
        raise ValueError('missing release URL')
    parsed = urlsplit(raw)
    if (parsed.scheme != 'https' or parsed.hostname != 'github.com'
            or parsed.username or parsed.password or parsed.port
            or parsed.query or parsed.fragment
            or not parsed.path.startswith('/ed0ard/CS2-Bot-Improver/releases/tag/')):
        raise ValueError('unexpected release URL')
    return raw


def _release_metadata() -> dict:
    request = urllib.request.Request(LATEST_API, headers={
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2026-03-10',
        'User-Agent': 'CS2Career-Manual-Update-Check',
    }, method='GET')
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise ValueError('unexpected GitHub response')
        content_length = response.headers.get('Content-Length')
        if content_length and not 0 <= int(content_length) <= MAX_RESPONSE_BYTES:
            raise ValueError('release response too large')
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError('release response too large')
    data = json.loads(payload.decode('utf-8'))
    if not isinstance(data, dict):
        raise ValueError('invalid release response')
    return data


def check_updates() -> dict:
    """Request metadata once, without changing or downloading local contents."""
    result = {
        'title': 'CS2 Bot Improver', 'version': '', 'url': RELEASES_URL,
        'current_version': '', 'update_available': False, 'checked': False,
        'reason': '',
    }
    try:
        current_version = _local_version()
        current = _stable_version(current_version)
        result['current_version'] = current_version
        if current is None:
            raise ValueError('invalid local version')
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        result['reason'] = '暂时无法读取本地人机增强版本，不影响现有安装。'
        return result
    try:
        release = _release_metadata()
        if release.get('draft') is not False or release.get('prerelease') is not False:
            result['reason'] = '上游没有返回正式发行版，现有安装保持不变。'
            return result
        version = release.get('tag_name')
        latest = _stable_version(version)
        if latest is None:
            result['reason'] = '上游版本号不是正式版本，现有安装保持不变。'
            return result
        url = _release_url(release.get('html_url'))
        title = release.get('name')
        title = ' '.join(title.split())[:160] if isinstance(title, str) else ''
        result.update({
            'title': title or 'CS2 Bot Improver ' + version.strip(),
            'version': version.strip().lstrip('vV'), 'url': url,
            'update_available': latest > current, 'checked': True,
            'reason': ('发现人机增强新版本，可前往官方页面查看。'
                       if latest > current else '当前人机增强已是最新版本。'),
        })
    except HTTPError as exc:
        if exc.code in (403, 429):
            result['reason'] = 'GitHub 暂时限制了更新查询，请稍后再检查。'
        elif exc.code == 404:
            result['reason'] = '暂时没有可检查的正式发行版，现有安装保持不变。'
        else:
            result['reason'] = '暂时无法连接 GitHub，请稍后再检查；不影响本地安装。'
    except (URLError, OSError, TimeoutError):
        result['reason'] = '暂时无法连接 GitHub，请稍后再检查；不影响本地安装。'
    except (ValueError, TypeError, KeyError, RecursionError):
        result['reason'] = '更新信息暂时无法读取，请稍后再检查；不影响本地安装。'
    return result


def check_cs2_updates() -> dict:
    """Compare official update announcements, never incompatible version domains.

    Steam BuildID, steam.inf ClientVersion and the UpToDateCheck API version are
    not interchangeable. News confirms an update exists, not that local native
    signatures have been tested. No CS2 installation is required for this query.
    """
    result = {'checked': False, 'update_available': False, 'title': '', 'date': '',
              'url': 'https://store.steampowered.com/news/app/730',
              'compatibility': 'not_live_verified', 'reason': ''}
    try:
        baseline = load_runtime_manifest().get('cs2_news_baseline', {})
        request = urllib.request.Request(STEAM_NEWS_API, headers={
            'User-Agent': 'CS2Career-Manual-Update-Check', 'Accept': 'application/json'})
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise ValueError('unexpected Steam response')
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError('Steam response too large')
        items = json.loads(payload)['appnews']['newsitems']
        updates = [item for item in items if isinstance(item, dict)
                   and item.get('feedname') == 'steam_community_announcements'
                   and item.get('title', '').strip().casefold() == 'counter-strike 2 update'
                   and isinstance(item.get('date'), int)
                   and str(item.get('gid', '')).isdigit()]
        if not updates:
            raise ValueError('No official CS2 update found')
        latest = max(updates, key=lambda item: item['date'])
        date = datetime.fromtimestamp(latest['date'], timezone.utc).strftime('%Y-%m-%d')
        newer = latest['date'] > int(baseline.get('timestamp', 0))
        result.update(checked=True, update_available=newer, title=latest['title'], date=date,
                      url='https://store.steampowered.com/news/app/730/view/' + str(latest['gid']),
                      reason=f'CS2 最近官方更新：{date}。' + (
                          '晚于本包核对日期，需要重新核对插件兼容性。' if newer else
                          '本包已核对该更新公告；实际游戏兼容性仍需安装后检查。'))
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        result['reason'] = 'CS2 官方更新暂时查询失败，请稍后重试。'
    return result


def check_all_updates() -> dict:
    # Both calls are independent, bounded and run outside the career save lock.
    with ThreadPoolExecutor(max_workers=2) as executor:
        improver = executor.submit(check_updates)
        cs2 = executor.submit(check_cs2_updates)
        result, game = improver.result(), cs2.result()
    result['cs2'] = game
    result['reason'] += '\n' + game['reason']
    return result


if __name__ == '__main__':
    print(json.dumps(check_all_updates(), ensure_ascii=False, indent=2))

