"""Independent CS2 exit watcher; no HTTP, ApplicationState or save imports.

It follows one game-directory generation. Closing the 3D program does not
cancel a running CS2 game's watcher, and a newer lease invalidates this one.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import time


def _read_lease(csgo):
    from cs2career.cs2.environment import read_lease
    return read_lease(csgo)


def _finish(csgo, generation):
    from cs2career.cs2.environment import finish_watch
    return finish_watch(csgo, generation)


def _started_at(value, fallback):
    if isinstance(value, str):
        try:
            instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if instant.tzinfo is None:
                instant = instant.replace(tzinfo=timezone.utc)
            return instant.timestamp()
        except ValueError:
            pass
    return fallback


def run_watch(csgo, generation, *, read=None, finish=None, probe=None,
              owner_probe=None, clock=None, sleep=None, interval=1.0,
              startup_timeout=90.0, max_iterations=None):
    """All boundaries are injectable: tests never launch or mutate a real game."""
    from cs2career.cs2.process_state import cs2_running, process_running
    read, finish = read or _read_lease, finish or _finish
    probe, owner_probe = probe or cs2_running, owner_probe or process_running
    clock, sleep = clock or time.time, sleep or time.sleep
    csgo = Path(csgo)
    seen_running, first_seen, iterations = False, clock(), 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        try:
            lease = read(csgo)
        except (OSError, ValueError, RuntimeError):
            # An atomic replacement, antivirus scan or brief permission issue
            # must not silently strand an enabled plugin environment.
            if max_iterations is None or iterations < max_iterations:
                sleep(interval)
            continue
        watch = lease.get('watch') or {}
        if (lease.get('generation') != generation or lease.get('mode') != 'enhanced'
                or watch.get('active') is not True):
            return dict(status='superseded', iterations=iterations)
        # A cached observation can be written by the owner before a watchdog
        # starts. The watcher also tracks its own observations independently.
        seen_running = seen_running or watch.get('seen_running') is True
        try:
            live = probe()
        except (OSError, ValueError, RuntimeError):
            live = None
        if live is True:
            seen_running = True
        elif live is False:
            dispatched = watch.get('mode') == 'dispatch'
            # Preparation can be slow. A worker spawned after dispatch gets a
            # full startup window rather than immediately undoing the mounts.
            dispatched_at = max(first_seen, _started_at(watch.get('started_at'), first_seen))
            elapsed = max(0.0, clock() - dispatched_at)
            owner = watch.get('owner_pid')
            owner_gone = False
            if watch.get('mode') == 'manual' and type(owner) is int:
                try:
                    owner_gone = owner_probe(owner) is False
                except (OSError, ValueError, RuntimeError):
                    pass
            should_finish = seen_running or dispatched and elapsed >= startup_timeout or owner_gone
            if should_finish:
                try:
                    outcome = finish(csgo, generation)
                except (OSError, ValueError, RuntimeError):
                    # Process or permissions may have changed since probing.
                    # Stay alive to retry, never assume unknown means closed.
                    pass
                else:
                    return dict(outcome, iterations=iterations, seen_running=seen_running)
        # live=None never grants a restore, even after startup timeout/owner exit.
        if max_iterations is None or iterations < max_iterations:
            sleep(interval)
    return dict(status='waiting', iterations=iterations, seen_running=seen_running)


def spawn_watch(csgo, generation, mode='dispatch', owner_pid=None, *, popen=None):
    """Spawn a hidden, independent worker which inherits no parent handles."""
    if mode not in ('dispatch', 'manual') or not isinstance(generation, str) or not generation:
        raise ValueError('CS2 环境守护参数不完整。')
    if owner_pid is not None and (type(owner_pid) is not int or owner_pid <= 0):
        raise ValueError('CS2 环境守护进程身份无效。')
    csgo = Path(csgo).resolve()
    if getattr(sys, 'frozen', False):
        executable = Path(sys.executable)
        if executable.name.casefold() != 'careerbackend.exe':
            executable = executable.parent / 'CareerBackend.exe'
        if not executable.is_file():
            raise FileNotFoundError('找不到独立的 CS2 环境守护后台。')
        command = [str(executable), '--cs2-environment-watchdog']
    else:
        script = Path(__file__).resolve()
        command = [sys.executable, '-B', str(script)]
    command += ['--csgo-path', str(csgo), '--generation', generation]
    flags = (0x08000000 | 0x00000200) if os.name == 'nt' else 0  # No window + own process group.
    arguments = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True, creationflags=flags)
    if os.name != 'nt':
        arguments['start_new_session'] = True
    return (popen or subprocess.Popen)(command, **arguments)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csgo-path', type=Path, required=True)
    parser.add_argument('--generation', required=True)
    args = parser.parse_args(argv)
    if not args.csgo_path.is_absolute() or not args.generation:
        parser.error('Use an absolute game/csgo path and a generation token')
    run_watch(args.csgo_path, args.generation)
    return 0


if __name__ == '__main__':
    # A source child is executed by path; add its project, never a save folder.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
