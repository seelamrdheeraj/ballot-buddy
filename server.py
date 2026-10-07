#!/usr/bin/env python3
"""Ballot Buddy server: serves the static site and app, plus the registration API.

Run:   python3 server.py            (reads .env next to this file, if present)
Env:   ADMIN_PASSWORD   unlocks the private admin page (required for sign-in)
       PORT             default 8765
       BIND             default 0.0.0.0 (so a phone on the same Wi-Fi can connect)
       BB_DB            SQLite path, default registrations.db next to this file
       BB_SECURE_COOKIE set to 1 when serving over HTTPS

Standard library only (http.server + sqlite3). No dependencies to install.

API (JSON in, JSON out, same origin):
  POST /api/register          {firstName, lastInitial, age}  -> 201 {ok, registration}
  POST /api/admin/login       {password}                      -> 200 + HttpOnly cookie
  POST /api/admin/logout                                      -> 200, cookie cleared
  GET  /api/admin/session                                     -> {authenticated, configured}
  GET  /api/registrations     (admin cookie required)         -> newest first
"""
import hmac
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
import unicodedata
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_dotenv(path):
    """Read KEY=value lines; never override variables already in the environment."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass


load_dotenv(os.path.join(ROOT, ".env"))

PORT = int(os.environ.get("PORT", "8765"))
BIND = os.environ.get("BIND", "0.0.0.0")
DB_PATH = os.path.abspath(os.environ.get("BB_DB") or os.path.join(ROOT, "registrations.db"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SECURE_COOKIE = os.environ.get("BB_SECURE_COOKIE") == "1"

MIN_AGE, MAX_AGE = 13, 120          # keep in sync with register.html
MAX_NAME = 40
MAX_BODY = 16 * 1024                # bytes; registration bodies are tiny
SESSION_TTL = 12 * 3600             # seconds an admin sign-in lasts
COOKIE = "bb_admin"
LOGIN_WINDOW, LOGIN_MAX_FAILURES = 600, 8   # per IP: 8 wrong passwords per 10 minutes

# Paths the static file server must never hand out.
PRIVATE_PREFIXES = ["/.git", "/.claude", "/.env", "/.frugal-fable", "/server.py", "/registrations.db"]
if DB_PATH.startswith(ROOT + os.sep):
    PRIVATE_PREFIXES.append("/" + os.path.relpath(DB_PATH, ROOT).replace(os.sep, "/"))
PRIVATE_PREFIXES = tuple(p.lower() for p in PRIVATE_PREFIXES)


# ---------- database ----------

def db():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS registrations (
                 id           INTEGER PRIMARY KEY AUTOINCREMENT,
                 first_name   TEXT    NOT NULL,
                 last_initial TEXT    NOT NULL,
                 age          INTEGER NOT NULL,
                 created_at   TEXT    NOT NULL
               )"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_registrations_created ON registrations(created_at DESC, id DESC)")
        conn.commit()
    finally:
        conn.close()


def row_to_dict(r):
    return {"id": r["id"], "firstName": r["first_name"], "lastInitial": r["last_initial"],
            "age": r["age"], "createdAt": r["created_at"]}


# ---------- validation (mirrors register.html) ----------

def _name_char(ch):
    return ch.isalpha() or ch in " '.-" or unicodedata.category(ch).startswith("M")


def validate(data):
    clean, errors = {}, {}

    first = data.get("firstName")
    first = first.strip() if isinstance(first, str) else ""
    if not first or len(first) > MAX_NAME or not first[0].isalpha() or not all(_name_char(c) for c in first):
        errors["firstName"] = "Enter your first name (letters only)."
    else:
        clean["firstName"] = first

    initial = data.get("lastInitial")
    initial = initial.strip() if isinstance(initial, str) else ""
    if len(initial) != 1 or not initial.isalpha():
        errors["lastInitial"] = "Enter one letter."
    else:
        clean["lastInitial"] = initial.upper()

    age = data.get("age")
    if isinstance(age, bool):
        age = None
    elif isinstance(age, str):
        age = int(age.strip()) if age.strip().isdecimal() else None
    elif isinstance(age, float):
        age = int(age) if age.is_integer() else None
    if not isinstance(age, int) or not (MIN_AGE <= age <= MAX_AGE):
        errors["age"] = f"Enter an age between {MIN_AGE} and {MAX_AGE}."
    else:
        clean["age"] = age

    return clean, errors


# ---------- admin sessions + login throttle (in memory; a restart signs everyone out) ----------

_lock = threading.Lock()
_sessions = {}   # token -> expiry timestamp
_failures = {}   # ip -> [failure timestamps]


def new_session():
    token = secrets.token_urlsafe(32)
    now = time.time()
    with _lock:
        for stale in [t for t, exp in _sessions.items() if exp < now]:
            del _sessions[stale]
        _sessions[token] = now + SESSION_TTL
    return token


def session_ok(token):
    if not token:
        return False
    with _lock:
        exp = _sessions.get(token)
        if exp and exp > time.time():
            return True
        _sessions.pop(token, None)
        return False


def drop_session(token):
    with _lock:
        _sessions.pop(token, None)


def too_many_failures(ip):
    now = time.time()
    with _lock:
        recent = [t for t in _failures.get(ip, []) if now - t < LOGIN_WINDOW]
        _failures[ip] = recent
        return len(recent) >= LOGIN_MAX_FAILURES


def note_failure(ip):
    with _lock:
        _failures.setdefault(ip, []).append(time.time())


def cookie_header(token):
    secure = "; Secure" if SECURE_COOKIE else ""
    return f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}{secure}"


def clear_cookie_header():
    return f"{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"


# ---------- HTTP ----------

class Handler(SimpleHTTPRequestHandler):
    server_version = "BallotBuddy/1.0"
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    # helpers -------------------------------------------------------------

    def send_json(self, status, payload, cookie=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        return True

    def read_body(self):
        """Return (dict, None) or (None, True) after an error response was sent."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None, self.send_json(400, {"ok": False, "error": "Bad request."})
        if length < 0:
            return None, self.send_json(400, {"ok": False, "error": "Bad request."})
        if length > MAX_BODY:
            return None, self.send_json(413, {"ok": False, "error": "Request too large."})
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return None, self.send_json(400, {"ok": False, "error": "Send a JSON body."})
        if not isinstance(data, dict):
            return None, self.send_json(400, {"ok": False, "error": "Send a JSON object."})
        return data, None

    def token(self):
        try:
            jar = SimpleCookie(self.headers.get("Cookie") or "")
            morsel = jar.get(COOKIE)
            return morsel.value if morsel else ""
        except Exception:
            return ""

    def is_private(self, path):
        p = os.path.normpath(path).replace(os.sep, "/").lower()
        return any(p == pre or p.startswith(pre + "/") or p.startswith(pre + "-") or p.startswith(pre + ".")
                   for pre in PRIVATE_PREFIXES)

    def end_headers(self):
        if getattr(self, "_static", False):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    # routing -------------------------------------------------------------

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/admin/session":
            return self.send_json(200, {"ok": True, "authenticated": session_ok(self.token()),
                                        "configured": bool(ADMIN_PASSWORD)})
        if path == "/api/registrations":
            return self.list_registrations()
        if path.startswith("/api/") or self.is_private(path):
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
        if path == "/api/register":
            return self.register()
        if path == "/api/admin/login":
            return self.login()
        if path == "/api/admin/logout":
            return self.logout()
        return self.send_json(404, {"ok": False, "error": "Not found."})

    # handlers ------------------------------------------------------------

    def register(self):
        data, err = self.read_body()
        if err:
            return
        clean, errors = validate(data)
        if errors:
            return self.send_json(400, {"ok": False, "error": "Please fix the highlighted fields.", "fields": errors})
        created = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        conn = db()
        try:
            cur = conn.execute(
                "INSERT INTO registrations (first_name, last_initial, age, created_at) VALUES (?, ?, ?, ?)",
                (clean["firstName"], clean["lastInitial"], clean["age"], created),
            )
            conn.commit()
            new_id = cur.lastrowid
        except sqlite3.Error as e:
            self.log_error("database write failed: %s", e)
            return self.send_json(500, {"ok": False, "error": "Couldn't save your registration. Try again."})
        finally:
            conn.close()
        registration = {"id": new_id, "firstName": clean["firstName"], "lastInitial": clean["lastInitial"],
                        "age": clean["age"], "createdAt": created}
        return self.send_json(201, {"ok": True, "registration": registration})

    def login(self):
        if not ADMIN_PASSWORD:
            return self.send_json(503, {"ok": False, "error": "Admin access isn't configured. Start the server with ADMIN_PASSWORD set."})
        ip = self.client_address[0]
        if too_many_failures(ip):
            return self.send_json(429, {"ok": False, "error": "Too many attempts. Try again in a minute."})
        data, err = self.read_body()
        if err:
            return
        password = data.get("password")
        password = password if isinstance(password, str) else ""
        if not hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8")):
            note_failure(ip)
            time.sleep(0.4)
            return self.send_json(401, {"ok": False, "error": "Wrong password."})
        return self.send_json(200, {"ok": True}, cookie=cookie_header(new_session()))

    def logout(self):
        drop_session(self.token())
        return self.send_json(200, {"ok": True}, cookie=clear_cookie_header())

    def list_registrations(self):
        if not session_ok(self.token()):
            return self.send_json(401, {"ok": False, "error": "Sign in to view registrations."})
        conn = db()
        try:
            rows = conn.execute(
                "SELECT id, first_name, last_initial, age, created_at FROM registrations "
                "ORDER BY created_at DESC, id DESC"
            ).fetchall()
        except sqlite3.Error as e:
            self.log_error("database read failed: %s", e)
            return self.send_json(500, {"ok": False, "error": "Couldn't load registrations. Try again."})
        finally:
            conn.close()
        regs = [row_to_dict(r) for r in rows]
        return self.send_json(200, {"ok": True, "count": len(regs), "registrations": regs})


def main():
    port = PORT
    if len(sys.argv) >= 3 and sys.argv[1] == "--port":
        port = int(sys.argv[2])
    init_db()
    server = ThreadingHTTPServer((BIND, port), Handler)
    server.daemon_threads = True
    print(f"Ballot Buddy is running at http://localhost:{port}/  (bound to {BIND}:{port})")
    print(f"  Site:      http://localhost:{port}/ballot-buddy-site.html")
    print(f"  Register:  http://localhost:{port}/register.html")
    print(f"  Admin:     http://localhost:{port}/admin.html")
    print(f"  Database:  {DB_PATH}")
    if not ADMIN_PASSWORD:
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
