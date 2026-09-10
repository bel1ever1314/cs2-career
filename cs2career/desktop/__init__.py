# coding=utf-8
"""Native desktop interface (lazy so Tcl can be prepared first on Windows)."""


def run_desktop() -> None:
    from .app import run_desktop as _run

    _run()


__all__ = ["run_desktop"]
