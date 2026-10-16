"""Offline bundle preparation, only in an explicitly requested match handoff.

The launch coordinator already persisted the nonce and intent. Status reads,
application startup and receipt replay never call this adapter.
"""
from pathlib import Path
import hashlib
import json


def _hash(path):
    from cs2career.paths import io_path
    try:
        with io_path(path).open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    except FileNotFoundError:
        return ''


def _installed(game, receipt):
    from cs2career.cs2 import launch
    expected = {name: sha for name, sha in receipt['files'].items()
                if Path(name).suffix.lower() in ('.dll', '.exe')}
    for plugin in ('CareerMatch', 'BotBuy', 'BotAimImprover'):
        for suffix in ('.dll', '.deps.json'):
            source = launch.vendor_root() / plugin / (plugin + suffix)
            sha = _hash(source)
            if not sha:
                raise FileNotFoundError('随包组件不完整：' + plugin + suffix)
            expected['addons/counterstrikesharp/plugins/' + plugin + '/' + plugin + suffix] = sha
    return all(_hash(game / name) == sha for name, sha in expected.items())


def prepare(cfg):
    from cs2career.cs2 import launch
    from cs2career.cs2 import runtime_compat as compat
    from cs2career.services import installation
    bundle = installation.bundle_root()
    if bundle is None:
        return cfg  # External-runtime editions retain their existing workflow.
    launch.require_cs2_closed('自动准备随包人机增强')
    game = launch.resolve_csgo_path(cfg.get('csgo_path') or '').resolve()
    if not launch.is_csgo_dir(game) or not (game / 'gameinfo.gi').is_file():
        raise ValueError('请先选择本机 CS2 目录。人机增强会在开赛时自动准备。')
    launch.require_installation_files(game)
    if game == bundle or game.is_relative_to(bundle) or bundle.is_relative_to(game):
        raise ValueError('人机增强来源不能与 CS2 安装目录重叠。')
    receipt = compat.validate_bundled_runtime(bundle)
    if receipt is None:
        raise ValueError('随包人机增强缺少校验清单，请使用完整测试包。')
    effective = dict(cfg, mod_source_path=str(bundle))
    if _installed(game, receipt):
        launch._matching_plugin_bytes.cache_clear()
        return effective
    root = installation._isolated_root()
    cached = compat.seed_bundled_runtime(root, bundle)
    runtime = compat.prepare_runtime(root, cached, game, allow_download=False)
    effective['mod_source_path'] = runtime['mod_dir']
    mod = Path(runtime['mod_dir'])
    targets = installation._snapshot_targets(game, mod, effective, False)
    backup, manifest = installation._snapshot(root, game, targets, runtime)
    try:
        launch.require_cs2_closed('自动准备随包人机增强')
        result = launch.install_mod(game, mod, config=effective)
        if not result.get('ok') or not _installed(game, receipt):
            raise RuntimeError('随包组件安装后核验失败，未启动 CS2。')
        from cs2career.cs2.environment import switch_environment
        switch_environment(game, 'normal')
        manifest['status'] = 'installed'
    except (OSError, ValueError, RuntimeError) as exc:
        manifest['status'] = 'failed'
        raise RuntimeError('自动准备未完成；备份保留在 ' + str(backup) + '。' + str(exc)) from exc
    finally:
        (backup / 'BACKUP_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    return effective
