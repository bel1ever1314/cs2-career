"""Game-only local inventory endpoint sharing the desktop's active career."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ..career import skins


def start_skin_api(career_getter):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):
            pass

        def do_GET(self):
            c = career_getter()
            sid = str(c.steam_id or '')
            valid = c.real_skins and sid and self.path==f'/api/equipped/v5/{sid}.json'
            body = skins.equipped_v5_body(c.inventory,c.equipped_ct or {},c.equipped_t or {}) if valid else {}
            blob = json.dumps(body).encode()
            self.send_response(200 if valid else 404)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)
    try:
        server = ThreadingHTTPServer(('127.0.0.1',skins.SKIN_API_PORT),Handler)
    except OSError:
        return None
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server
