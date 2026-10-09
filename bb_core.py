"""Shared logic for the Ballot Buddy registration API.

Used by two front doors that expose the same five routes:
  * server.py            local development, stores registrations in SQLite
  * api/**/*.py          Vercel Functions, stores registrations in Vercel Blob (private)

Standard library only. Validation, admin sessions, storage backends and the
HTTP adapter all live here so the two deployments cannot drift apart.

Routes (JSON in, JSON out):
  POST  /api/register         {firstName, lastInitial, age, email, password} -> 201 {ok, user} + HttpOnly cookie
  POST  /api/login            {email, password}               -> 200 {ok, user, state} + HttpOnly cookie
  POST  /api/logout                                           -> 200, cookie cleared
  GET   /api/me               (user cookie)                   -> {authenticated, user, state, updatedAt}; refreshes the cookie
  PUT   /api/me               {state, baseRev, uid}           -> saves the app's state; 409 when baseRev is stale
  PATCH /api/me               {firstName?, lastInitial?, age?, email?, currentPassword?, newPassword?} -> {ok, user}
  POST  /api/admin/login      {password}                      -> 200 + HttpOnly cookie
  POST  /api/admin/logout                                     -> 200, cookie cleared
  GET   /api/admin/session                                    -> {authenticated, configured}
  GET   /api/registrations    (admin cookie required)         -> newest first

Accounts: one record per user (profile, PBKDF2 password hash) keyed by a random uid, a separate
state document per user (the app's saved state with a revision counter, so a state write can never
clobber a credential change), plus an email -> uid index. The user session is a signed, stateless
cookie (uid.sv.expires.sig; sv changes with the password, which signs other devices out) whose key
comes from SESSION_SECRET or a secret created once and kept in the store, so nothing about the
admin password affects voters' sign-ins.
"""
import base64
import hashlib
import hmac
import json
import os
import re
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

USER_COOKIE = "bb_user"
USER_SESSION_TTL = 30 * 24 * 3600   # seconds a voter stays signed in without opening the app
MAX_EMAIL = 254
MAX_PASSWORD = 200
MAX_STATE_BODY = 256 * 1024         # bytes; the app's saved state (picks, swipes, chat) is a few KB
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    """Password from the environment. Optional: the admin page can create one on first use instead."""
    return os.environ.get("ADMIN_PASSWORD", "")


PBKDF2_ITERATIONS = 200_000
MIN_PASSWORD = 8
PASSWORD_CACHE_TTL = 30
_pw_cache = {"at": 0.0, "record": None}


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS).hex()
    return {"salt": salt, "hash": digest, "iterations": PBKDF2_ITERATIONS}


def password_matches(password, record):
    try:
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(record["salt"]),
                                     int(record.get("iterations", PBKDF2_ITERATIONS))).hex()
        return hmac.compare_digest(digest, record["hash"])
    except (KeyError, ValueError, TypeError):
        return False


def stored_password(fresh=False):
    """The password record created from the admin page's first-run setup, or None (cached briefly)."""
    now = time.time()
    if not fresh and now - _pw_cache["at"] < PASSWORD_CACHE_TTL:
        return _pw_cache["record"]
    store = get_store()
    if store is None:
        return None
    try:
        raw = store.get_setting("admin_password")
    except StorageError as e:
        print(f"admin password read failed: {e}", flush=True)
        return _pw_cache["record"]
    record = None
    if raw:
        try:
            record = json.loads(raw)
        except ValueError:
            record = None
    _pw_cache.update(at=now, record=record)
    return record


def admin_configured():
    return bool(admin_password()) or stored_password() is not None


def verify_admin_password(password):
    env = admin_password()
    if env:
        return hmac.compare_digest(password.encode("utf-8"), env.encode("utf-8"))
    record = stored_password()
    return record is not None and password_matches(password, record)


def on_vercel():
    return bool(os.environ.get("VERCEL"))


def secure_cookies():
    return os.environ.get("BB_SECURE_COOKIE") == "1" or on_vercel()


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------- validation (mirrors register.html) ----------

def _name_char(ch):
    return ch.isalpha() or ch in " '.-" or unicodedata.category(ch).startswith("M")


PROFILE_FIELDS = ("firstName", "lastInitial", "age")
ACCOUNT_FIELDS = PROFILE_FIELDS + ("email", "password")


def normalize_email(value):
    return unicodedata.normalize("NFC", value).strip().lower() if isinstance(value, str) else ""


def validate(data, fields=PROFILE_FIELDS):
    """Check the named fields of a request body; returns (clean, errors)."""
    clean, errors = {}, {}

    if "firstName" in fields:
        first = data.get("firstName")
        first = unicodedata.normalize("NFC", first).replace("\u2019", "'").strip() if isinstance(first, str) else ""
        if not first or len(first) > MAX_NAME or not first[0].isalpha() or not all(_name_char(c) for c in first):
            errors["firstName"] = "Enter your first name (letters only)."
        else:
            clean["firstName"] = first

    if "lastInitial" in fields:
        initial = data.get("lastInitial")
        initial = initial.strip() if isinstance(initial, str) else ""
        if len(initial) != 1 or not initial.isalpha():
            errors["lastInitial"] = "Enter one letter."
        else:
            clean["lastInitial"] = initial.upper()

    if "age" in fields:
        age = data.get("age")
        if isinstance(age, bool):
            age = None
        elif isinstance(age, str):
            age = int(age.strip()) if age.strip().isdecimal() and len(age.strip()) <= 4 else None
        elif isinstance(age, float):
            age = int(age) if age.is_integer() else None
        if not isinstance(age, int) or not (MIN_AGE <= age <= MAX_AGE):
            errors["age"] = f"Enter an age between {MIN_AGE} and {MAX_AGE}."
        else:
            clean["age"] = age

    if "email" in fields:
        email = normalize_email(data.get("email"))
        if not email or len(email) > MAX_EMAIL or not EMAIL_RE.match(email):
            errors["email"] = "Enter a valid email address."
        else:
            clean["email"] = email

    if "password" in fields:
        password = data.get("password")
        password = password if isinstance(password, str) else ""
        if len(password) < MIN_PASSWORD or len(password) > MAX_PASSWORD:
            errors["password"] = f"Use at least {MIN_PASSWORD} characters."
        else:
            clean["password"] = password

    return clean, errors


def email_key(email):
    return hashlib.sha256(email.encode("utf-8")).hexdigest()


# ---------- admin sessions: stateless, signed cookies ----------
# The signature key derives from ADMIN_PASSWORD (or SESSION_SECRET if set), so
# a token survives server restarts and serverless cold starts, and changing
# the password signs every admin out.

def _session_key():
    base = os.environ.get("SESSION_SECRET") or admin_password()
    if not base:
        record = stored_password()
        base = record["hash"] if record else ""
    return hashlib.sha256(("bb-session:" + base).encode("utf-8")).digest()


def make_session_token():
    expires = str(int(time.time()) + SESSION_TTL)
    sig = hmac.new(_session_key(), expires.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{expires}.{sig}"


def session_valid(token):
    if not token or not admin_configured():
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


# ---------- user sessions: stateless, signed cookies, 30-day sliding ----------

_secret_cache = {"value": None}


def session_secret():
    """SESSION_SECRET from the environment, else a random secret created once and kept in the store.

    Raises StorageError when the store cannot be read, so a hiccup never looks like 'signed out'.
    Returns "" only when no store is configured at all.
    """
    env = os.environ.get("SESSION_SECRET")
    if env:
        return env
    if _secret_cache["value"]:
        return _secret_cache["value"]
    store = get_store()
    if store is None:
        return ""
    value = store.get_secret()
    if not value:
        store.create_secret(secrets.token_hex(32))   # create-once; a losing racer reads the winner's
        value = store.get_secret()
    if not value:
        raise StorageError("session secret could not be created")
    _secret_cache["value"] = value
    return value


def _user_session_key():
    return hashlib.sha256(("bb-user-session:" + session_secret()).encode("utf-8")).digest()


def session_version(record):
    """Part of the password salt; baked into tokens so a password change signs every other device out."""
    return str((record.get("pw") or {}).get("salt", ""))[:8] or "0"


def make_user_token(record):
    uid, sv = record["uid"], session_version(record)
    expires = str(int(time.time()) + USER_SESSION_TTL)
    sig = hmac.new(_user_session_key(), f"{uid}.{sv}.{expires}".encode("ascii"), hashlib.sha256).hexdigest()
    return f"{uid}.{sv}.{expires}.{sig}"


def parse_user_token(token):
    """(uid, sv) for a well-formed, correctly signed, unexpired token, else None. May raise StorageError."""
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 4:
        return None
    uid, sv, expires, sig = parts
    if not uid.isalnum() or not sv.isalnum() or not expires.isdigit() or not sig or not session_secret():
        return None
    expected = hmac.new(_user_session_key(), f"{uid}.{sv}.{expires}".encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected) or int(expires) <= time.time():
        return None
    return uid, sv


def user_cookie_header(token):
    secure = "; Secure" if secure_cookies() else ""
    return f"{USER_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={USER_SESSION_TTL}{secure}"


def clear_user_cookie_header():
    return f"{USER_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"


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
            conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS users (uid TEXT PRIMARY KEY, record TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS emails (email_key TEXT PRIMARY KEY, uid TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS states (uid TEXT PRIMARY KEY, doc TEXT NOT NULL)")
            conn.commit()
        finally:
            conn.close()

    # -- users --

    def get_user(self, uid):
        conn = self._connect()
        try:
            row = conn.execute("SELECT record FROM users WHERE uid = ?", (uid,)).fetchone()
            return json.loads(row["record"]) if row else None
        except (sqlite3.Error, ValueError) as e:
            raise StorageError(str(e)) from e
        finally:
            conn.close()

    def put_user(self, uid, record):
        conn = self._connect()
        try:
            conn.execute("INSERT INTO users (uid, record) VALUES (?, ?) ON CONFLICT(uid) DO UPDATE SET record = excluded.record",
                         (uid, json.dumps(record, ensure_ascii=False)))
            conn.commit()
        except sqlite3.Error as e:
            raise StorageError(str(e)) from e
        finally:
            conn.close()

    def get_state(self, uid):
        conn = self._connect()
        try:
            row = conn.execute("SELECT doc FROM states WHERE uid = ?", (uid,)).fetchone()
            return json.loads(row["doc"]) if row else None
        except (sqlite3.Error, ValueError) as e:
            raise StorageError(str(e)) from e
        finally:
            conn.close()

    def put_state(self, uid, doc):
        conn = self._connect()
        try:
            conn.execute("INSERT INTO states (uid, doc) VALUES (?, ?) ON CONFLICT(uid) DO UPDATE SET doc = excluded.doc",
                         (uid, json.dumps(doc, ensure_ascii=False)))
            conn.commit()
        except sqlite3.Error as e:
            raise StorageError(str(e)) from e
        finally:
            conn.close()

    def get_secret(self):
        return self.get_setting("session_secret")

    def create_secret(self, value):
        conn = self._connect()
        try:
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('session_secret', ?)", (value,))
            conn.commit()
        except sqlite3.Error as e:
            raise StorageError(str(e)) from e
        finally:
            conn.close()

    def uid_for_email(self, key):
        conn = self._connect()
        try:
            row = conn.execute("SELECT uid FROM emails WHERE email_key = ?", (key,)).fetchone()
            return row["uid"] if row else None
        except sqlite3.Error as e:
            raise StorageError(str(e)) from e
        finally:
            conn.close()

    def index_email(self, key, uid):
        conn = self._connect()
        try:
            conn.execute("INSERT INTO emails (email_key, uid) VALUES (?, ?) ON CONFLICT(email_key) DO UPDATE SET uid = excluded.uid", (key, uid))
            conn.commit()
        except sqlite3.Error as e:
            raise StorageError(str(e)) from e
        finally:
            conn.close()

    def unindex_email(self, key, uid):
        conn = self._connect()
        try:
            conn.execute("DELETE FROM emails WHERE email_key = ? AND uid = ?", (key, uid))
            conn.commit()
        except sqlite3.Error as e:
            raise StorageError(str(e)) from e
        finally:
            conn.close()

    def get_setting(self, key):
        conn = self._connect()
        try:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None
        except sqlite3.Error as e:
            raise StorageError(str(e)) from e
        finally:
            conn.close()

    def set_setting(self, key, value):
        conn = self._connect()
        try:
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
            conn.commit()
        except sqlite3.Error as e:
            raise StorageError(str(e)) from e
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
        # A read-write token carries the store id (vercel_blob_rw_<store>_<secret>); BLOB_STORE_ID is the
        # fallback for OIDC tokens and may carry a "store_" prefix the hostname does not use.
        self.store_id = (parts[3] if parts[0:3] == ["vercel", "blob", "rw"] and len(parts) > 3 else "") \
            or (store_id or "").removeprefix("store_")

    # -- HTTP --

    def _request(self, method, url, headers=None, body=None, timeout=20, ok404=False):
        req = urlrequest.Request(url, data=body, method=method)
        req.add_header("authorization", f"Bearer {self.token}")
        req.add_header("x-api-version", self.VERSION)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urlrequest.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urlerror.HTTPError as e:
            if e.code == 404 and ok404:
                return 404, b""
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

    # -- blob contents --
    # Private blobs are read the way the official SDK's get() does it: a token-authenticated GET on
    # the store's private hostname (cache=0 skips the CDN, since user records are overwritten in place).

    def _blob_url(self, pathname):
        if not self.store_id:
            raise StorageError("Blob store id unknown; set BLOB_STORE_ID")
        return f"https://{self.store_id}.private.blob.vercel-storage.com/{urlparse.quote(pathname)}?cache=0"

    def get_doc(self, pathname):
        """Parsed JSON contents of a blob, or None when it does not exist."""
        status, raw = self._request("GET", self._blob_url(pathname), ok404=True)
        if status == 404:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise StorageError(f"blob {pathname} is not valid JSON") from e

    def put_doc(self, pathname, value, overwrite=True):
        url = f"{self.API}?{urlparse.urlencode({'pathname': pathname})}"
        headers = {"x-content-type": "application/json", "x-add-random-suffix": "0",
                   "x-allow-overwrite": "1" if overwrite else "0", "x-cache-control-max-age": "0",
                   "x-vercel-blob-access": "private", "content-type": "application/json"}
        self._request("PUT", url, headers, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def delete_blob(self, pathname):
        body = json.dumps({"urls": [pathname]}).encode("utf-8")
        self._request("POST", f"{self.API}/delete", {"content-type": "application/json"}, body)

    # -- users --
    # users/<uid>.json holds the whole record; emails/<sha256(email)>_<uid>.json is the sign-in index,
    # resolved through the list API so a login costs one list plus one GET.

    USERS_PREFIX = "users/"
    STATES_PREFIX = "states/"
    EMAILS_PREFIX = "emails/"
    SECRET_PATH = "settings/session_secret.json"

    def get_user(self, uid):
        return self.get_doc(f"{self.USERS_PREFIX}{uid}.json")

    def put_user(self, uid, record):
        self.put_doc(f"{self.USERS_PREFIX}{uid}.json", record)

    def get_state(self, uid):
        return self.get_doc(f"{self.STATES_PREFIX}{uid}.json")

    def put_state(self, uid, doc):
        self.put_doc(f"{self.STATES_PREFIX}{uid}.json", doc)

    def get_secret(self):
        doc = self.get_doc(self.SECRET_PATH)
        return doc.get("value") if isinstance(doc, dict) else None

    def create_secret(self, value):
        try:
            self.put_doc(self.SECRET_PATH, {"value": value}, overwrite=False)
        except StorageError as e:   # already created by another instance: the caller reads it back
            print(f"session secret create skipped: {e}", flush=True)

    def uid_for_email(self, key):
        best = None
        for blob in self._list(f"{self.EMAILS_PREFIX}{key}_"):
            name = blob.get("pathname", "")
            if not name.startswith(f"{self.EMAILS_PREFIX}{key}_") or not name.endswith(".json"):
                continue
            uid = name[len(self.EMAILS_PREFIX) + len(key) + 1:-5]
            stamp = blob.get("uploadedAt") or ""
            if uid.isalnum() and (best is None or stamp > best[0]):
                best = (stamp, uid)
        return best[1] if best else None

    def index_email(self, key, uid):
        self.put_doc(f"{self.EMAILS_PREFIX}{key}_{uid}.json", {"uid": uid})

    def unindex_email(self, key, uid):
        self.delete_blob(f"{self.EMAILS_PREFIX}{key}_{uid}.json")

    # -- settings --
    # Small settings are also encoded into the pathname and read back through the list API
    # (settings/<key>_<base64url(value)>.json), which predates get_doc and needs no download.
    # Legacy settings/<key>.json blobs are ignored.

    SETTINGS_PREFIX = "settings/"

    def _list(self, prefix):
        params = {"prefix": prefix, "limit": "100", "mode": "expanded"}
        _, raw = self._request("GET", f"{self.API}?{urlparse.urlencode(params)}")
        try:
            return json.loads(raw).get("blobs", [])
        except ValueError as e:
            raise StorageError("Blob API returned invalid JSON") from e

    def get_setting(self, key):
        best = None
        for blob in self._list(f"{self.SETTINGS_PREFIX}{key}_"):
            name = blob.get("pathname", "")
            if not name.startswith(f"{self.SETTINGS_PREFIX}{key}_") or not name.endswith(".json"):
                continue
            b64 = name[len(self.SETTINGS_PREFIX) + len(key) + 1:-5]
            try:
                value = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                continue
            stamp = blob.get("uploadedAt") or ""
            if best is None or stamp > best[0]:
                best = (stamp, value)
        return best[1] if best else None

    def set_setting(self, key, value):
        b64 = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
        pathname = f"{self.SETTINGS_PREFIX}{key}_{b64}.json"
        url = f"{self.API}?{urlparse.urlencode({'pathname': pathname})}"
        headers = {"x-content-type": "application/json", "x-add-random-suffix": "0", "x-allow-overwrite": "1",
                   "x-vercel-blob-access": "private", "content-type": "application/json"}
        self._request("PUT", url, headers, value.encode("utf-8"))

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

def public_user(record):
    return {k: record.get(k) for k in ("uid", "firstName", "lastInitial", "age", "email", "createdAt")}


EMPTY_STATE = {"state": {}, "rev": 0, "updatedAt": 0}


def me_payload(record, sdoc):
    sdoc = sdoc or EMPTY_STATE
    return {"ok": True, "authenticated": True, "user": public_user(record),
            "state": sdoc.get("state") or {}, "rev": int(sdoc.get("rev") or 0), "updatedAt": sdoc.get("updatedAt") or 0}


def load_user(token):
    """(store, record) for a valid user cookie; record is None when signed out, unknown, or the
    password changed since the token was issued. May raise StorageError."""
    store = get_store()
    if store is None:
        return None, None
    parsed = parse_user_token(token)
    if not parsed:
        return store, None
    uid, sv = parsed
    record = store.get_user(uid)
    if record is None or not hmac.compare_digest(sv, session_version(record)):
        return store, None
    return store, record


def email_taken(store, key, email, uid=None):
    """True when the index maps this email to a live account other than uid. A stale index entry
    (its record is gone or now carries another email) does not count and gets overwritten."""
    other = store.uid_for_email(key)
    if not other or other == uid:
        return False
    rec = store.get_user(other)
    return bool(rec) and rec.get("email") == email


def wrong_user(data, record):
    """The client names the uid it believes it is syncing; a tab left open after another sign-in must not
    write one person's data into another's account."""
    uid = data.get("uid")
    return isinstance(uid, str) and uid != "" and uid != record["uid"]


WRONG_USER = {"ok": False, "wrongUser": True, "error": "A different account is signed in on this device."}


SIGNED_OUT = {"ok": True, "authenticated": False}
STORAGE_DOWN = {"ok": False, "error": "Couldn't reach your account right now. Try again."}


def api_register(data):
    clean, errors = validate(data, ACCOUNT_FIELDS)
    if errors:
        return 400, {"ok": False, "error": "Please fix the highlighted fields.", "fields": errors}, None
    store = get_store()
    if store is None:
        return 503, {"ok": False, "error": NOT_SET_UP}, None
    key = email_key(clean["email"])
    try:
        if email_taken(store, key, clean["email"]):
            return 409, {"ok": False, "error": "That email already has an account. Sign in instead.",
                         "fields": {"email": "Already registered. Sign in instead."}}, None
        now = utc_now_iso()
        uid = secrets.token_hex(12)
        record = {"uid": uid, "email": clean["email"], "firstName": clean["firstName"],
                  "lastInitial": clean["lastInitial"], "age": clean["age"], "pw": hash_password(clean["password"]),
                  "createdAt": now, "updatedAt": now}
        store.put_user(uid, record)
        store.index_email(key, uid)
        cookie = user_cookie_header(make_user_token(record))
        try:   # the admin page's sign-up log keeps working unchanged
            store.add(clean["firstName"], clean["lastInitial"], clean["age"], now)
        except StorageError as e:
            print(f"registration log write failed: {e}", flush=True)
    except StorageError as e:
        print(f"account create failed: {e}", flush=True)
        return 500, {"ok": False, "error": "Couldn't create your account. Try again."}, None
    return 201, {"ok": True, "user": public_user(record)}, cookie


def api_login_user(data, ip):
    store = get_store()
    if store is None:
        return 503, {"ok": False, "error": NOT_SET_UP}, None
    if too_many_failures("u:" + ip):
        return 429, {"ok": False, "error": "Too many attempts. Try again in a few minutes."}, None
    email = normalize_email(data.get("email"))
    password = data.get("password")
    password = password if isinstance(password, str) else ""
    wrong = (401, {"ok": False, "error": "Email or password is incorrect."}, None)
    if not email or not password:
        return wrong
    try:
        uid = store.uid_for_email(email_key(email))
        record = store.get_user(uid) if uid else None
        if not record or record.get("email") != email or not password_matches(password, record.get("pw") or {}):
            note_failure("u:" + ip)
            time.sleep(0.4)
            return wrong
        sdoc = store.get_state(record["uid"])
        cookie = user_cookie_header(make_user_token(record))
    except StorageError as e:
        print(f"login read failed: {e}", flush=True)
        return 500, STORAGE_DOWN, None
    return 200, me_payload(record, sdoc), cookie


def api_logout_user():
    return 200, {"ok": True}, clear_user_cookie_header()


def api_me(token):
    try:
        store, record = load_user(token)
        if store is None:
            return 503, {"ok": False, "error": NOT_SET_UP}, None
        if record is None:
            return 200, SIGNED_OUT, clear_user_cookie_header() if token else None
        sdoc = store.get_state(record["uid"])
        cookie = user_cookie_header(make_user_token(record))   # sliding expiry
    except StorageError as e:
        print(f"account read failed: {e}", flush=True)
        return 500, STORAGE_DOWN, None   # never clears the cookie: the session may well be fine
    return 200, me_payload(record, sdoc), cookie


def api_me_put(token, data):
    state = data.get("state")
    if not isinstance(state, dict):
        return 400, {"ok": False, "error": "Send {state: {...}}."}
    base = data.get("baseRev")
    if base is not None and (isinstance(base, bool) or not isinstance(base, int) or base < 0):
        return 400, {"ok": False, "error": "baseRev must be a non-negative integer."}
    try:
        store, record = load_user(token)
        if store is None:
            return 503, {"ok": False, "error": NOT_SET_UP}
        if record is None:
            return 401, {"ok": False, "authenticated": False, "error": "Sign in again."}
        if wrong_user(data, record):
            return 409, WRONG_USER
        current = store.get_state(record["uid"]) or EMPTY_STATE
        if base is not None and base != int(current.get("rev") or 0):
            # Another device (or tab) wrote first: hand back the newer copy instead of overwriting it.
            return 409, {"ok": False, "conflict": True, "state": current.get("state") or {},
                         "rev": int(current.get("rev") or 0), "updatedAt": current.get("updatedAt") or 0}
        state.pop("user", None)
        doc = {"state": state, "rev": int(current.get("rev") or 0) + 1, "updatedAt": int(time.time() * 1000)}
        store.put_state(record["uid"], doc)
    except StorageError as e:
        print(f"state write failed: {e}", flush=True)
        return 500, STORAGE_DOWN
    return 200, {"ok": True, "rev": doc["rev"], "updatedAt": doc["updatedAt"]}


def api_me_patch(token, data):
    wanted = tuple(f for f in PROFILE_FIELDS + ("email",) if f in data)
    clean, errors = validate(data, wanted)
    new_password = data.get("newPassword")
    if new_password is not None:
        pw_clean, pw_errors = validate({"password": new_password}, ("password",))
        if pw_errors:
            errors["newPassword"] = pw_errors["password"]
        else:
            clean["newPassword"] = pw_clean["password"]
    if errors:
        return 400, {"ok": False, "error": "Please fix the highlighted fields.", "fields": errors}, None
    try:
        store, record = load_user(token)
        if store is None:
            return 503, {"ok": False, "error": NOT_SET_UP}, None
        if record is None:
            return 401, {"ok": False, "authenticated": False, "error": "Sign in again."}, None
        if wrong_user(data, record):
            return 409, WRONG_USER, None
        email_change = "email" in clean and clean["email"] != record.get("email")
        if email_change or "newPassword" in clean:
            current = data.get("currentPassword")
            if not isinstance(current, str) or not password_matches(current, record.get("pw") or {}):
                return 403, {"ok": False, "error": "Your current password is incorrect.",
                             "fields": {"currentPassword": "Enter your current password."}}, None
        old_key = email_key(record["email"])
        if email_change:
            new_key = email_key(clean["email"])
            if email_taken(store, new_key, clean["email"], record["uid"]):
                return 409, {"ok": False, "error": "That email already has an account.",
                             "fields": {"email": "Already in use by another account."}}, None
            store.index_email(new_key, record["uid"])
        for k in ("firstName", "lastInitial", "age", "email"):
            if k in clean:
                record[k] = clean[k]
        cookie = None
        if "newPassword" in clean:
            record["pw"] = hash_password(clean["newPassword"])   # new salt: every other device's token stops verifying
            cookie = user_cookie_header(make_user_token(record))
        record["updatedAt"] = utc_now_iso()
        store.put_user(record["uid"], record)
        if email_change:
            try:
                store.unindex_email(old_key, record["uid"])
            except StorageError as e:
                print(f"old email unindex failed: {e}", flush=True)   # a stale index entry is ignored by email_taken and login
    except StorageError as e:
        print(f"profile write failed: {e}", flush=True)
        return 500, STORAGE_DOWN, None
    return 200, {"ok": True, "user": public_user(record)}, cookie


def api_login(data, ip):
    if not admin_configured():
        if get_store() is not None:
            return 409, {"ok": False, "error": "No admin password yet. Create one first."}, None
        return 503, {"ok": False, "error": "Admin access isn't configured. Start the server with ADMIN_PASSWORD set."}, None
    if too_many_failures(ip):
        return 429, {"ok": False, "error": "Too many attempts. Try again in a minute."}, None
    password = data.get("password")
    password = password if isinstance(password, str) else ""
    if not verify_admin_password(password):
        note_failure(ip)
        time.sleep(0.4)
        return 401, {"ok": False, "error": "Wrong password."}, None
    return 200, {"ok": True}, cookie_header(make_session_token())


def api_setup(data):
    """First-run: create the admin password when none exists (env or stored)."""
    store = get_store()
    if store is None:
        return 503, {"ok": False, "error": NOT_SET_UP}, None
    if admin_password() or stored_password(fresh=True) is not None:
        return 409, {"ok": False, "error": "The admin password was already created."}, None
    password = data.get("password")
    password = password if isinstance(password, str) else ""
    if len(password) < MIN_PASSWORD or len(password) > 200:
        return 400, {"ok": False, "error": f"Use at least {MIN_PASSWORD} characters."}, None
    try:
        store.set_setting("admin_password", json.dumps(hash_password(password)))
    except StorageError as e:
        print(f"admin password write failed: {e}", flush=True)
        return 500, {"ok": False, "error": "Couldn't save the password. Try again."}, None
    stored_password(fresh=True)
    return 200, {"ok": True}, cookie_header(make_session_token())


def api_logout():
    return 200, {"ok": True}, clear_cookie_header()


def api_session(token):
    # "env" lists the NAMES of relevant variables (never values) to make hosting setup debuggable.
    names = sorted(k for k in os.environ
                   if k.startswith(("BLOB", "ADMIN_", "VERCEL_OIDC", "VERCEL_ENV", "VERCEL_BLOB", "SESSION_SECRET")))
    storage = get_store() is not None
    configured = admin_configured()
    return 200, {"ok": True, "authenticated": session_valid(token), "configured": configured,
                 "storage": storage, "setupNeeded": storage and not configured, "env": names}


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

    def read_json(self, limit=MAX_BODY):
        """Return (dict, None), or (None, True) after an error response was sent."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None, self.send_json(400, {"ok": False, "error": "Bad request."})
        if length < 0:
            return None, self.send_json(400, {"ok": False, "error": "Bad request."})
        if length > limit:
            return None, self.send_json(413, {"ok": False, "error": "Request too large."})
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if length and ctype != "application/json":
            # A plain HTML form cannot send this type, so a cross-site form post can never reach a handler.
            self.drain_body(length)
            return None, self.send_json(415, {"ok": False, "error": "Send JSON (Content-Type: application/json)."})
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError, RecursionError):
            return None, self.send_json(400, {"ok": False, "error": "Send a JSON body."})
        if not isinstance(data, dict):
            return None, self.send_json(400, {"ok": False, "error": "Send a JSON object."})
        return data, None

    def drain_body(self, length=None):
        """Consume a request body a route does not need, so a keep-alive connection stays in sync."""
        if length is None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
        if 0 < length <= MAX_STATE_BODY:
            self.rfile.read(length)

    def session_token(self, name=COOKIE):
        try:
            jar = SimpleCookie(self.headers.get("Cookie") or "")
            morsel = jar.get(name)
            return morsel.value if morsel else ""
        except Exception:
            return ""

    def user_token(self):
        return self.session_token(USER_COOKIE)

    def client_ip(self):
        forwarded = self.headers.get("x-forwarded-for") or self.headers.get("x-real-ip")
        if forwarded:
            return forwarded.split(",")[0].strip()
        addr = getattr(self, "client_address", None)
        return addr[0] if addr else "?"

    def handle_api(self, method):
        route = self.route or urlparse.urlsplit(self.path).path.removeprefix("/api/").strip("/")
        if method != "GET" and (self.headers.get("Sec-Fetch-Site") or "").strip().lower() == "cross-site":
            self.drain_body()
            return self.send_json(403, {"ok": False, "error": "Cross-site requests are not allowed."})
        if route == "register" and method == "POST":
            data, err = self.read_json()
            if err:
                return
            return self.send_json(*api_register(data))
        if route == "login" and method == "POST":
            data, err = self.read_json()
            if err:
                return
            return self.send_json(*api_login_user(data, self.client_ip()))
        if route == "logout" and method == "POST":
            self.drain_body()
            return self.send_json(*api_logout_user())
        if route == "me" and method == "GET":
            return self.send_json(*api_me(self.user_token()))
        if route == "me" and method == "PUT":
            data, err = self.read_json(MAX_STATE_BODY)
            if err:
                return
            return self.send_json(*api_me_put(self.user_token(), data))
        if route == "me" and method == "PATCH":
            data, err = self.read_json()
            if err:
                return
            status, payload, cookie = api_me_patch(self.user_token(), data)
            return self.send_json(status, payload, cookie)
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
            self.drain_body()
            status, payload, cookie = api_logout()
            return self.send_json(status, payload, cookie)
        if route == "admin/setup" and method == "POST":
            data, err = self.read_json()
            if err:
                return
            status, payload, cookie = api_setup(data)
            return self.send_json(status, payload, cookie)
        if route in ("register", "login", "logout", "me", "registrations", "admin/session", "admin/login", "admin/logout", "admin/setup"):
            return self.send_json(405, {"ok": False, "error": "Method not allowed."})
        return self.send_json(404, {"ok": False, "error": "Not found."})


class ApiHandler(ApiMixin, BaseHTTPRequestHandler):
    """Base class for the Vercel functions in api/. Subclasses set `route`."""

    def do_GET(self):
        self.handle_api("GET")

    def do_POST(self):
        self.handle_api("POST")

    def do_PUT(self):
        self.handle_api("PUT")

    def do_PATCH(self):
        self.handle_api("PATCH")

    def log_message(self, fmt, *args):  # Vercel captures stdout; keep it quiet
        pass
