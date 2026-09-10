# coding=utf-8
"""Make the stdlib Tcl/Tk runtime reliable from paths containing CJK text.

Some Windows Python installs discover Tcl through an ANSI path even though the
application itself is Unicode-aware.  Copying the read-only scripts to the
ASCII temp directory fixes source launches. PyInstaller uses its own bundled
copy and skips this branch.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


def prepare_tk_runtime() -> None:
    if getattr(sys, "frozen", False) or (os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY")):
        return
    source = Path(sys.base_prefix) / "tcl"
    tcl_src = source / "tcl8.6"
    tk_src = source / "tk8.6"
    if not (tcl_src / "init.tcl").is_file() or not (tk_src / "tk.tcl").is_file():
        return
    base = Path(tempfile.gettempdir()) / "CS2Career-tk-8.6"
    tcl_dst = base / "tcl8.6"
    tk_dst = base / "tk8.6"
    if not (tcl_dst / "init.tcl").is_file():
        shutil.copytree(tcl_src, tcl_dst, dirs_exist_ok=True)
    if not (tk_dst / "tk.tcl").is_file():
        shutil.copytree(tk_src, tk_dst, dirs_exist_ok=True)
    os.environ["TCL_LIBRARY"] = str(tcl_dst)
    os.environ["TK_LIBRARY"] = str(tk_dst)
