# coding=utf-8
"""CS2 Career launcher. Desktop by default; --web keeps the old UI optional."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

def main() -> None:
    if '--self-test' in sys.argv:
        from cs2career.release_smoke import run
        output = Path(sys.argv[sys.argv.index('--self-test') + 1])
        run(output)
        return
    if '--playtest' in sys.argv:
        import os
        root = Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
        os.environ['CS2CAREER_SAVE_DIR'] = str(root / '.qa' / 'playtest' / 'save')
        os.environ['CS2CAREER_EXTENSION_DIR'] = str(root / '.qa' / 'playtest' / 'extensions')
        os.environ['CS2CAREER_NO_GAME'] = '1'
    if '--design-preview' in sys.argv:
        import os
        root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
        os.environ['CS2CAREER_SAVE_DIR'] = str(root / '.qa' / 'design-preview' / 'save')
        os.environ['CS2CAREER_EXTENSION_DIR'] = str(root / '.qa' / 'design-preview' / 'extensions')
        from cs2career.design_preview import run
        run(server_only='--server-only' in sys.argv)
        return
    if "--web" in sys.argv:
        from cs2career.desktop.webview_app import run
        try:
            run(browser=True)
        except KeyboardInterrupt:
            print("\n关闭。")
        return
    from cs2career.desktop.webview_app import run_desktop

    run_desktop()


if __name__ == "__main__":
    main()
