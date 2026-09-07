# coding=utf-8
"""Build the 1.4 release: exe + docs. Bot Improver is not bundled."""

from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEP = ";" if os.name == "nt" else ":"
OUT_NAME = "CS2Career-1.4"


def _pyi() -> int:
    try:
        import PyInstaller.__main__ as pyi
    except ImportError:
        print("缺少 PyInstaller：py -3 -m pip install pyinstaller")
        return 1

    for stale in ("build", "dist"):
        shutil.rmtree(ROOT / stale, ignore_errors=True)

    args = [
        str(ROOT / "main.py"),
        "--name", "CS2Career",
        "--onefile",
        "--console",
        "--clean",
        "--noconfirm",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--add-data", f"{ROOT / 'cs2career' / 'data'}{SEP}data",
        "--add-data", f"{ROOT / 'cs2career' / 'web' / 'static'}{SEP}web{os.sep}static",
        "--exclude-module", "tkinter",
        "--exclude-module", "unittest",
        "--exclude-module", "pydoc",
    ]
    for name in ("CareerMatch", "InventorySimulator", "InvsimCareer"):
        vendor = ROOT / "vendor" / name
        if vendor.is_dir():
            args += ["--add-data", f"{vendor}{SEP}vendor{os.sep}{name}"]
    pyi.run(args)
    exe = ROOT / "dist" / "CS2Career.exe"
    return 0 if exe.is_file() else 1


def _zip_dir(folder: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in folder.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(folder.parent))


def main() -> int:
    if _pyi() != 0:
        print("打包 exe 失败")
        return 1

    release = ROOT / "release" / OUT_NAME
    shutil.rmtree(release, ignore_errors=True)
    release.mkdir(parents=True)

    shutil.copy2(ROOT / "dist" / "CS2Career.exe", release / "CS2Career.exe")
    for name in ("游玩说明.txt", "添加人机增强.txt", "README.md"):
        src = ROOT / name
        if src.is_file():
            shutil.copy2(src, release / name)

    zip_path = ROOT / "release" / f"{OUT_NAME}.zip"
    _zip_dir(release, zip_path)

    exe = release / "CS2Career.exe"
    print(f"\n发布文件夹：{release}")
    print(f"压缩包：{zip_path}  ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"exe：{exe.stat().st_size / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
