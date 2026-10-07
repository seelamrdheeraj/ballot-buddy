#!/usr/bin/env python3
"""Ballot Buddy local server: serves the static site and app, plus the registration API.

Run:   python3 server.py            (reads .env next to this file, if present)
Env:   ADMIN_PASSWORD   unlocks the private admin page (required for sign-in)
       PORT             default 8765
       BIND             default 0.0.0.0 (so a phone on the same Wi-Fi can connect)
       BB_DB            SQLite path, default registrations.db next to this file
       BB_SECURE_COOKIE set to 1 when serving over HTTPS
       BLOB_READ_WRITE_TOKEN  optional: store registrations in Vercel Blob instead of SQLite

Standard library only. The API itself lives in bb_core.py and is shared with
the Vercel functions in api/, so local and hosted behave the same.
"""
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import bb_core
from bb_core import ApiMixin, ROOT

bb_core.load_dotenv(os.path.join(ROOT, ".env"))

PORT = int(os.environ.get("PORT", "8765"))
BIND = os.environ.get("BIND", "0.0.0.0")

# Paths the static file server must never hand out.
PRIVATE_PREFIXES = ["/.git", "/.claude", "/.env", "/.frugal-fable", "/server.py", "/bb_core.py",
                    "/api", "/registrations.db", "/vercel.json"]
_db = os.path.abspath(os.environ.get("BB_DB") or os.path.join(ROOT, "registrations.db"))
if _db.startswith(ROOT + os.sep):
    PRIVATE_PREFIXES.append("/" + os.path.relpath(_db, ROOT).replace(os.sep, "/"))
PRIVATE_PREFIXES = tuple(p.lower() for p in PRIVATE_PREFIXES)


class Handler(ApiMixin, SimpleHTTPRequestHandler):
    server_version = "BallotBuddy/1.1"
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def is_private(self, path):
        p = os.path.normpath(path).replace(os.sep, "/").lower()
        return any(p == pre or p.startswith(pre + "/") or p.startswith(pre + "-") or p.startswith(pre + ".")
                   for pre in PRIVATE_PREFIXES)

    def end_headers(self):
        if getattr(self, "_static", False):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            return self.handle_api("GET")
        if self.is_private(path):
            return self.send_json(404, {"ok": False, "error": "Not found."})
        self._static = True
        return super().do_GET()

    def do_HEAD(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/") or self.is_private(path):
            return self.send_json(404, {"ok": False, "error": "Not found."})
        self._static = True
        return super().do_HEAD()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            return self.handle_api("POST")
        return self.send_json(404, {"ok": False, "error": "Not found."})


def main():
    port = PORT
    if len(sys.argv) >= 3 and sys.argv[1] == "--port":
        port = int(sys.argv[2])
    store = bb_core.get_store()
    server = ThreadingHTTPServer((BIND, port), Handler)
    server.daemon_threads = True
    print(f"Ballot Buddy is running at http://localhost:{port}/  (bound to {BIND}:{port})")
    print(f"  Site:      http://localhost:{port}/ballot-buddy-site.html")
    print(f"  Register:  http://localhost:{port}/register.html")
    print(f"  Admin:     http://localhost:{port}/admin.html")
    if isinstance(store, bb_core.SQLiteStore):
        print(f"  Storage:   SQLite at {store.path}")
    elif store is not None:
        print("  Storage:   Vercel Blob (BLOB_READ_WRITE_TOKEN is set)")
    if not bb_core.admin_password():
        print("  WARNING: ADMIN_PASSWORD is not set, so the admin page cannot sign in. "
              "Put ADMIN_PASSWORD=... in .env (see .env.example) or export it.", file=sys.stderr)
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
