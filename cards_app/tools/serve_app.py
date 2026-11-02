"""Serve the built app (cards_app/dist) to my phone through Tailscale.

Listens only on this Mac (127.0.0.1:8767). `tailscale serve --https=8444`
passes on requests from devices on the tailnet, with HTTPS, which iOS needs for
home-screen apps and offline caching. Nothing on the local Wi-Fi or the
internet can reach it. Runs in the background via
~/Library/LaunchAgents/local.chesscards.app-server.plist.

It also runs update.py when the app's "Get new games" button asks
(POST /api/update), and says how that run is going (GET /api/update).

Stdlib only. Run the service with a Python you installed (setup_phone.sh
takes PYTHON=..., e.g. uv's), not /usr/bin/python3: macOS privacy protection
stops the system Python from reading ~/Documents when launchd starts it.
"""

import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlsplit

from updater import Updater

ROOT = Path(__file__).resolve().parent.parent / "dist"
PORT = 8767
TYPES = {".webmanifest": "application/manifest+json", ".webp": "image/webp", ".js": "text/javascript"}
# Files that name other files: if these were cached, a new build would never be noticed.
SHELL = {"index.html", "sw.js", "manifest.webmanifest", "registerSW.js"}


def resolve(root: Path, url_path: str) -> Optional[Path]:
    """The file under root a request may see, or None."""
    rest = unquote(urlsplit(url_path).path).lstrip("/") or "index.html"
    target = (root / rest).resolve()
    if root.resolve() not in target.parents or not target.is_file():
        return None
    return target


def cache_control(rel: str) -> str:
    if rel in SHELL or rel.startswith("workbox-"):
        return "no-cache"
    if rel.startswith("assets/"):
        return "public, max-age=31536000, immutable"  # file names carry a content hash
    return "public, max-age=86400"


UPDATER = Updater()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path == "/api/update":
            self.send_json(UPDATER.status())
        else:
            self.respond(body=True)

    def do_POST(self):
        if urlsplit(self.path).path == "/api/update":
            self.send_json(UPDATER.request())
        else:
            self.send_error(404)

    def send_json(self, value):
        data = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        self.respond(body=False)

    def respond(self, body: bool):
        path = resolve(ROOT, self.path)
        if path is None:
            self.send_error(404)
            return
        rel = path.relative_to(ROOT.resolve()).as_posix()
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", TYPES.get(path.suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache_control(rel))
        self.end_headers()
        if body:
            self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass  # quiet: one line per request is noise


def main() -> None:
    if not (ROOT / "index.html").is_file():
        sys.exit(f"no build at {ROOT}; run `pnpm build` in cards_app/ first")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"serving {ROOT} on http://127.0.0.1:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
