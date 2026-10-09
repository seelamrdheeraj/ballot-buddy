#!/usr/bin/env python3
"""End-to-end check of the account API against a running server.py.

Usage: python3 tools/test_accounts.py [http://localhost:8768]
Creates one throwaway account (random email), exercises every route, and prints PASS/FAIL per step.
"""
import json
import secrets
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8768"


class Client:
    def __init__(self):
        self.jar = CookieJar()
        self.open = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar)).open

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with self.open(req) as r:
                return r.status, json.loads(r.read() or b"{}"), r.headers
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}"), e.headers

    def cookie(self, name):
        return next((c for c in self.jar if c.name == name), None)


fails = 0


def check(label, cond, detail=""):
    global fails
    fails += 0 if cond else 1
    print(("PASS " if cond else "FAIL ") + label + ("" if cond else f"  -> {detail}"))


email = f"test-{secrets.token_hex(4)}@example.com"
a = Client()

s, j, _ = a.call("POST", "/api/register", {"firstName": "Ana", "lastInitial": "R", "age": 19, "email": "bad", "password": "short"})
check("register rejects bad email/password", s == 400 and set(j.get("fields", {})) == {"email", "password"}, j)

s, j, h = a.call("POST", "/api/register", {"firstName": "Ana", "lastInitial": "r", "age": "19", "email": " " + email.upper() + " ", "password": "correct horse"})
check("register creates account", s == 201 and j["user"]["email"] == email and j["user"]["lastInitial"] == "R" and j["user"]["age"] == 19, j)
ck = a.cookie("bb_user")
check("register sets HttpOnly user cookie", ck is not None and ck.has_nonstandard_attr("HttpOnly") and "SameSite" in h.get("Set-Cookie", ""), h.get("Set-Cookie"))
uid = j.get("user", {}).get("uid")

s, j, _ = Client().call("POST", "/api/register", {"firstName": "Ana", "lastInitial": "R", "age": 19, "email": email, "password": "correct horse"})
check("duplicate email is refused", s == 409 and "email" in j.get("fields", {}), j)

s, j, _ = a.call("GET", "/api/me")
check("me returns the signed-in user", s == 200 and j["authenticated"] and j["user"]["uid"] == uid and j["state"] == {}, j)

s, j, _ = a.call("PUT", "/api/me", {"state": {"zip": "95391", "screen": "measures", "user": {"uid": "spoof"}}, "baseRev": 0, "uid": uid})
check("state is saved (rev 1)", s == 200 and j["ok"] and j["rev"] == 1 and j["updatedAt"] > 0, j)
s, j, _ = a.call("GET", "/api/me")
check("state round-trips without a client-supplied user", s == 200 and j["state"] == {"zip": "95391", "screen": "measures"} and j["rev"] == 1, j)

s, j, _ = a.call("PUT", "/api/me", {"state": {"zip": "00000"}, "baseRev": 0, "uid": uid})
check("stale baseRev is refused with the current copy", s == 409 and j.get("conflict") and j["rev"] == 1 and j["state"]["zip"] == "95391", j)
s, j, _ = a.call("PUT", "/api/me", {"state": {"zip": "95391", "screen": "home"}, "baseRev": 1, "uid": uid})
check("current baseRev is accepted (rev 2)", s == 200 and j["rev"] == 2, j)
s, j, _ = a.call("PUT", "/api/me", {"state": {"zip": "x"}, "baseRev": 2, "uid": "someoneelse"})
check("a write for another uid is refused", s == 409 and j.get("wrongUser"), j)
s, j, _ = a.call("PATCH", "/api/me", {"firstName": "Zed", "uid": "someoneelse"})
check("a profile edit for another uid is refused", s == 409 and j.get("wrongUser"), j)

req = urllib.request.Request(BASE + "/api/me", data=b'{"state":{}}', method="PUT", headers={"Content-Type": "text/plain"})
try:
    with a.open(req) as r:
        s = r.status
except urllib.error.HTTPError as e:
    s = e.code
check("non-JSON content type is refused (CSRF form post)", s == 415, s)
req = urllib.request.Request(BASE + "/api/login", data=b'{"email":"x@example.com","password":"12345678"}', method="POST",
                             headers={"Content-Type": "application/json", "Sec-Fetch-Site": "cross-site"})
try:
    with Client().open(req) as r:
        s = r.status
except urllib.error.HTTPError as e:
    s = e.code
check("cross-site POST is refused", s == 403, s)

for path in ("/.env", "/%2eenv", "/registrations%2edb", "/%2egit/config", "/bb_core.py", "/%62b_core.py"):
    req = urllib.request.Request(BASE + path)
    try:
        with Client().open(req) as r:
            s, body = r.status, r.read()[:40]
    except urllib.error.HTTPError as e:
        s, body = e.code, e.read()[:40]
    check(f"private path {path} is hidden", s == 404 and b"Not found" in body, (s, body))

s, j, _ = a.call("PATCH", "/api/me", {"firstName": "Anita", "age": 20})
check("profile name/age update", s == 200 and j["user"]["firstName"] == "Anita" and j["user"]["age"] == 20, j)

other_device = Client()
s, j, _ = other_device.call("POST", "/api/login", {"email": email, "password": "correct horse"})
check("second device signs in before the password change", s == 200 and j["authenticated"], j)

new_email = "new-" + email
s, j, _ = a.call("PATCH", "/api/me", {"email": new_email})
check("email change needs current password", s == 403 and "currentPassword" in j.get("fields", {}), j)
s, j, _ = a.call("PATCH", "/api/me", {"email": new_email, "currentPassword": "wrong", "newPassword": "new password 9"})
check("wrong current password is refused", s == 403, j)
s, j, _ = a.call("PATCH", "/api/me", {"email": new_email, "currentPassword": "correct horse", "newPassword": "new password 9"})
check("email + password change", s == 200 and j["user"]["email"] == new_email, j)
s, j, _ = a.call("GET", "/api/me")
check("the device that changed the password stays signed in", s == 200 and j["authenticated"] and j["user"]["email"] == new_email, j)
s, j, _ = other_device.call("GET", "/api/me")
check("other devices are signed out by the password change", s == 200 and j["authenticated"] is False, j)

s, j, _ = Client().call("POST", "/api/login", {"email": email, "password": "new password 9"})
check("old email no longer signs in", s == 401, j)
s, j, _ = Client().call("POST", "/api/login", {"email": new_email, "password": "correct horse"})
check("old password no longer signs in", s == 401, j)

b = Client()
s, j, _ = b.call("POST", "/api/login", {"email": new_email.upper(), "password": "new password 9"})
check("login returns user + saved state + rev", s == 200 and j["user"]["uid"] == uid and j["state"].get("zip") == "95391" and j["rev"] == 2, j)

s, j, _ = b.call("POST", "/api/logout")
s2, j2, _ = b.call("GET", "/api/me")
check("logout clears the session", s == 200 and s2 == 200 and j2["authenticated"] is False, (j, j2))

s, j, _ = Client().call("GET", "/api/me")
check("no cookie -> signed out", s == 200 and j["authenticated"] is False, j)
s, j, _ = Client().call("PUT", "/api/me", {"state": {}})
check("state write without session is 401", s == 401, j)

forged = Client()
forged.jar.set_cookie(__import__("http.cookiejar").cookiejar.Cookie(0, "bb_user", f"{uid}.0.9999999999.deadbeef", None, False, "localhost", True, False, "/", True, False, None, False, None, None, {}))
s, j, _ = forged.call("GET", "/api/me")
check("forged cookie is rejected", s == 200 and j["authenticated"] is False, j)

s, j, _ = Client().call("POST", "/api/register", {"firstName": "Bo", "lastInitial": "Q", "age": "9" * 5000, "email": "bo-" + email, "password": "long enough"})
check("absurd age string is a 400, not a crash", s == 400 and "age" in j.get("fields", {}), (s, str(j)[:80]))
deep = "[" * 3000 + "]" * 3000   # past Python's recursion limit, inside the body limit
req = urllib.request.Request(BASE + "/api/login", data=deep.encode(), method="POST", headers={"Content-Type": "application/json"})
try:
    with Client().open(req) as r:
        s = r.status
except urllib.error.HTTPError as e:
    s = e.code
check("deeply nested JSON is a 400, not a crash", s == 400, s)

print("\nALL PASS" if not fails else f"\n{fails} FAILED")
sys.exit(1 if fails else 0)
