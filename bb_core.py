"""Shared logic for the Ballot Buddy registration API.

Used by two front doors that expose the same five routes:
  * server.py            local development, stores registrations in SQLite
  * api/**/*.py          Vercel Functions, stores registrations in Vercel Blob (private)

Standard library only. Validation, admin sessions, storage backends and the
HTTP adapter all live here so the two deployments cannot drift apart.

Routes (JSON in, JSON out):
  POST /api/register          {firstName, lastInitial, age}  -> 201 {ok, registration}
  POST /api/admin/login       {password}                      -> 200 + HttpOnly cookie
  POST /api/admin/logout                                      -> 200, cookie cleared
  GET  /api/admin/session                                     -> {authenticated, configured}
  GET  /api/registrations     (admin cookie required)         -> newest first
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import unicodedata
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

ROOT = os.path.dirname(os.path.abspath(__file__))

MIN_AGE, MAX_AGE = 13, 120          # keep in sync with register.html
MAX_NAME = 40
MAX_BODY = 16 * 1024                # bytes; registration bodies are tiny
SESSION_TTL = 12 * 3600             # seconds an admin sign-in lasts
COOKIE = "bb_admin"
LOGIN_WINDOW, LOGIN_MAX_FAILURES = 600, 8   # per IP, per process


# ---------- configuration ----------

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


def admin_password():
    return os.environ.get("ADMIN_PASSWORD", "")


def on_vercel():
    return bool(os.environ.get("VERCEL"))


def secure_cookies():
    return os.environ.get("BB_SECURE_COOKIE") == "1" or on_vercel()


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


# ---------- admin sessions: stateless, signed cookies ----------
# The signature key derives from ADMIN_PASSWORD (or SESSION_SECRET if set), so
# a token survives server restarts and serverless cold starts, and changing
# the password signs every admin out.

def _session_key():
    base = os.environ.get("SESSION_SECRET") or admin_password()
    return hashlib.sha256(("bb-session:" + base).encode("utf-8")).digest()


def make_session_token():
    expires = str(int(time.time()) + SESSION_TTL)
    sig = hmac.new(_session_key(), expires.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{expires}.{sig}"


def session_valid(token):
    if not token or not admin_password():
        return False
    expires, _, sig = token.partition(".")
    if not expires.isdigit() or not sig:
        return False
    expected = hmac.new(_session_key(), expires.encode("ascii"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected) and int(expires) > time.time()


def cookie_header(token):
    secure = "; Secure" if secure_cookies() else ""
    return f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}{secure}"


def clear_cookie_header():
    return f"{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"


# ---------- login throttle (per process; best effort on serverless) ----------

_lock = threading.Lock()
_failures = {}   # ip -> [failure timestamps]


def too_many_failures(ip):
    now = time.time()
    with _lock:
        recent = [t for t in _failures.get(ip, []) if now - t < LOGIN_WINDOW]
        _failures[ip] = recent
        return len(recent) >= LOGIN_MAX_FAILURES


def note_failure(ip):
    with _lock:
        _failures.setdefault(ip, []).append(time.time())


# ---------- storage backends ----------

class StorageError(Exception):
    pass


class SQLiteStore:
    """Local development: one file next to the project."""

    def __init__(self, path):
        self.path = path
        conn = self._connect()
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

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def add(self, first_name, last_initial, age, created_at):
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO registrations (first_name, last_initial, age, created_at) VALUES (?, ?, ?, ?)",
                (first_name, last_initial, age, created_at),
            )
            conn.commit()
            new_id = cur.lastrowid
        except sqlite3.Error as e:
            raise StorageError(str(e)) from e
        finally:
            conn.close()
        return {"id": new_id, "firstName": first_name, "lastInitial": last_initial, "age": age, "createdAt": created_at}

    def newest_first(self):
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, first_name, last_initial, age, created_at FROM registrations "
                "ORDER BY created_at DESC, id DESC"
            ).fetchall()
        except sqlite3.Error as e:
            raise StorageError(str(e)) from e
        finally:
            conn.close()
        return [{"id": r["id"], "firstName": r["first_name"], "lastInitial": r["last_initial"],
                 "age": r["age"], "createdAt": r["created_at"]} for r in rows]


class BlobStore:
    """Vercel Blob (private store), one small JSON blob per registration.

    Speaks the same HTTP the official SDK speaks (API version 11). The record
    is also encoded into the blob's pathname, so the admin list needs only the
    list call and never has to download each blob.
    """

    API = "https://vercel.com/api/blob"
    VERSION = "11"
    PREFIX = "registrations/"

    def __init__(self, token, store_id=None):
        self.token = token
        parts = token.split("_")
        self.store_id = store_id or (parts[3] if len(parts) > 3 else "")

    # -- HTTP --

    def _request(self, method, url, headers=None, body=None, timeout=20):
        req = urlrequest.Request(url, data=body, method=method)
        req.add_header("authorization", f"Bearer {self.token}")
        req.add_header("x-api-version", self.VERSION)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urlrequest.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urlerror.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            raise StorageError(f"Blob API {e.code}: {detail}") from e
        except (urlerror.URLError, TimeoutError, OSError) as e:
            raise StorageError(f"Blob API unreachable: {e}") from e

    # -- encoding --

    @classmethod
    def _pathname(cls, record):
        compact = record["createdAt"].replace("-", "").replace(":", "")
        payload = json.dumps([record["firstName"], record["lastInitial"], record["age"]], ensure_ascii=False)
        b64 = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
        return f"{cls.PREFIX}{compact}_{secrets.token_hex(4)}_{b64}.json"

    @classmethod
    def _decode(cls, pathname):
        name = pathname[len(cls.PREFIX):]
        if not name.endswith(".json"):
            return None
        try:
            compact, rand, b64 = name[:-5].split("_", 2)
            padded = b64 + "=" * (-len(b64) % 4)
            first, initial, age = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
            created = f"{compact[0:4]}-{compact[4:6]}-{compact[6:8]}T{compact[9:11]}:{compact[11:13]}:{compact[13:15]}Z"
        except (ValueError, IndexError, TypeError):
            return None
        return {"id": pathname, "firstName": first, "lastInitial": initial, "age": age, "createdAt": created,
                "_sort": (compact, rand)}

    # -- operations --

    def add(self, first_name, last_initial, age, created_at):
        record = {"firstName": first_name, "lastInitial": last_initial, "age": age, "createdAt": created_at}
        pathname = self._pathname(record)
        url = f"{self.API}?{urlparse.urlencode({'pathname': pathname})}"
        headers = {
            "x-content-type": "application/json",
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "0",
            "x-vercel-blob-access": "private",
            "content-type": "application/json",
        }
        self._request("PUT", url, headers, json.dumps(record).encode("utf-8"))
        record["id"] = pathname
        return record

    def newest_first(self):
        records, cursor = [], None
        for _ in range(100):  # 100 pages x 1000 blobs is far beyond this app's scale
            params = {"prefix": self.PREFIX, "limit": "1000", "mode": "expanded"}
            if cursor:
                params["cursor"] = cursor
            _, raw = self._request("GET", f"{self.API}?{urlparse.urlencode(params)}")
            try:
                page = json.loads(raw)
            except ValueError as e:
                raise StorageError("Blob API returned invalid JSON") from e
            for blob in page.get("blobs", []):
                rec = self._decode(blob.get("pathname", ""))
                if rec:
                    records.append(rec)
            cursor = page.get("cursor") if page.get("hasMore") else None
            if not cursor:
                break
        records.sort(key=lambda r: r["_sort"], reverse=True)
        for r in records:
            del r["_sort"]
        return records


def get_store():
    """Pick the backend from the environment. Returns None when nothing usable is configured."""
    rw = os.environ.get("BLOB_READ_WRITE_TOKEN") or os.environ.get("VERCEL_BLOB_READ_WRITE_TOKEN")
    if rw:
        return BlobStore(rw, os.environ.get("BLOB_STORE_ID"))
    oidc, store_id = os.environ.get("VERCEL_OIDC_TOKEN"), os.environ.get("BLOB_STORE_ID")
    if oidc and store_id:
        return BlobStore(oidc, store_id)
    if on_vercel():
        return None
    return SQLiteStore(os.environ.get("BB_DB") or os.path.join(ROOT, "registrations.db"))


NOT_SET_UP = "Registration isn't set up on this server yet. Connect a Vercel Blob store to the project."


# ---------- route handlers: pure functions returning (status, payload[, cookie]) ----------

def api_register(data):
    clean, errors = validate(data)
    if errors:
        return 400, {"ok": False, "error": "Please fix the highlighted fields.", "fields": errors}
    store = get_store()
    if store is None:
        return 503, {"ok": False, "error": NOT_SET_UP}
    try:
        reg = store.add(clean["firstName"], clean["lastInitial"], clean["age"], utc_now_iso())
    except StorageError as e:
        print(f"registration write failed: {e}", flush=True)
        return 500, {"ok": False, "error": "Couldn't save your registration. Try again."}
    return 201, {"ok": True, "registration": reg}


def api_login(data, ip):
    if not admin_password():
        return 503, {"ok": False, "error": "Admin access isn't configured. Start the server with ADMIN_PASSWORD set."}, None
    if too_many_failures(ip):
        return 429, {"ok": False, "error": "Too many attempts. Try again in a minute."}, None
    password = data.get("password")
    password = password if isinstance(password, str) else ""
    if not hmac.compare_digest(password.encode("utf-8"), admin_password().encode("utf-8")):
        note_failure(ip)
        time.sleep(0.4)
        return 401, {"ok": False, "error": "Wrong password."}, None
    return 200, {"ok": True}, cookie_header(make_session_token())


def api_logout():
    return 200, {"ok": True}, clear_cookie_header()


def api_session(token):
    # "env" lists the NAMES of relevant variables (never values) to make hosting setup debuggable.
    names = sorted(k for k in os.environ
                   if k.startswith(("BLOB", "ADMIN_", "VERCEL_OIDC", "VERCEL_ENV", "VERCEL_BLOB", "SESSION_SECRET")))
    return 200, {"ok": True, "authenticated": session_valid(token), "configured": bool(admin_password()),
                 "storage": get_store() is not None, "env": names}


def api_list(token):
    if not session_valid(token):
        return 401, {"ok": False, "error": "Sign in to view registrations."}
    store = get_store()
    if store is None:
        return 503, {"ok": False, "error": NOT_SET_UP}
    try:
        regs = store.newest_first()
    except StorageError as e:
        print(f"registration read failed: {e}", flush=True)
        return 500, {"ok": False, "error": "Couldn't load registrations. Try again."}
    return 200, {"ok": True, "count": len(regs), "registrations": regs}


# ---------- HTTP adapter shared by server.py and the Vercel functions ----------

class ApiMixin:
    """Mix into a BaseHTTPRequestHandler. Set `route` or let it come from the URL."""

    route = None

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

    def read_json(self):
        """Return (dict, None), or (None, True) after an error response was sent."""
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

    def session_token(self):
        try:
            jar = SimpleCookie(self.headers.get("Cookie") or "")
            morsel = jar.get(COOKIE)
            return morsel.value if morsel else ""
        except Exception:
            return ""

    def client_ip(self):
        forwarded = self.headers.get("x-forwarded-for") or self.headers.get("x-real-ip")
        if forwarded:
            return forwarded.split(",")[0].strip()
        addr = getattr(self, "client_address", None)
        return addr[0] if addr else "?"

    def handle_api(self, method):
        route = self.route or urlparse.urlsplit(self.path).path.removeprefix("/api/").strip("/")
        if route == "register" and method == "POST":
            data, err = self.read_json()
            if err:
                return
            return self.send_json(*api_register(data))
        if route == "registrations" and method == "GET":
            return self.send_json(*api_list(self.session_token()))
        if route == "admin/session" and method == "GET":
            return self.send_json(*api_session(self.session_token()))
        if route == "admin/login" and method == "POST":
            data, err = self.read_json()
            if err:
                return
            status, payload, cookie = api_login(data, self.client_ip())
            return self.send_json(status, payload, cookie)
        if route == "admin/logout" and method == "POST":
            status, payload, cookie = api_logout()
            return self.send_json(status, payload, cookie)
        if route in ("register", "registrations", "admin/session", "admin/login", "admin/logout"):
            return self.send_json(405, {"ok": False, "error": "Method not allowed."})
        return self.send_json(404, {"ok": False, "error": "Not found."})


class ApiHandler(ApiMixin, BaseHTTPRequestHandler):
    """Base class for the Vercel functions in api/. Subclasses set `route`."""

    def do_GET(self):
        self.handle_api("GET")

    def do_POST(self):
        self.handle_api("POST")

    def log_message(self, fmt, *args):  # Vercel captures stdout; keep it quiet
        pass
