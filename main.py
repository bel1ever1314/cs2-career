# coding=utf-8
"""CS2 Career — launcher. Starts the local server and opens the UI."""

from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cs2career.web import free_port, serve  # noqa: E402


def main() -> None:
    port = free_port(8768)
    url = f"http://127.0.0.1:{port}/"
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    try:
        serve(port)
    except KeyboardInterrupt:
        print("\n关闭。")


if __name__ == "__main__":
    main()
