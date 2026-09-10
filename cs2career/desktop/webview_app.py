"""Window lifecycle only. All game state belongs to the injected local server."""
import sys
import threading
from pathlib import Path


def run(state=None, *, preview=False, browser=False):
    dependencies = Path(__file__).resolve().parents[2] / '.desktop-deps'
    if dependencies.is_dir():
        sys.path.insert(0, str(dependencies))
    if not browser:
        try:
            import webview
        except ImportError as exc:
            raise RuntimeError('桌面依赖未安装。请运行 py -3 -m pip install -r requirements-desktop.txt') from exc
    from ..web.server import create_server, start_skin_api
    server = create_server(state)
    server.preview = preview
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    bridge = None if preview or server.game_disabled else start_skin_api(server.state)
    url = f'http://127.0.0.1:{server.server_port}/?token={server.token}'
    try:
        if browser:
            import webbrowser
            webbrowser.open(url)
            worker.join()
        else:
            webview.create_window('CS2 Career · '+('隔离设计预览' if preview else '隔离流程测试' if server.game_disabled else '生涯中心'), url,
                                  width=1440, height=900, min_size=(1060, 680), background_color='#101318',
                                  text_select=True, zoomable=True)
            # Explicit renderer: never silently use deprecated MSHTML.
            webview.start(gui='edgechromium', private_mode=True, debug=False)
    finally:
        server.shutdown()
        worker.join(timeout=5)
        with server.state_lock:
            server.state.persist()
        server.server_close()
        if bridge:
            bridge.shutdown()
            bridge.server_close()


def run_desktop():
    try:
        run()
    except Exception as exc:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f'{exc}\n\n桌面需要 Microsoft Edge WebView2 Runtime。\n请安装运行环境后重试；不会自动打开浏览器。', 'CS2 Career 启动失败', 0x10)
        raise
