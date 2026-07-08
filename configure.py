#!/usr/bin/env python3
"""
Gandalf seeder. Casdoor only imports init_data.json on a first-ever empty-DB
boot, which is brittle across restarts. This script seeds the same objects
(the eUnionX org, JWT cert, the trader/warroom/mobile OIDC apps, users, roles)
through Casdoor's REST API as the admin, and rebrands the built-in admin console
to eUnionX/Gandalf. It is idempotent: re-running it just reports "exists".

Usage: python3 configure.py [base_url] [admin_password]
  base_url        default http://localhost:18000
  admin_password  default 123 (the fresh-install Casdoor admin password)
Reads init_data.json from the same directory.
"""
import json, os, sys, urllib.request, urllib.error, http.cookiejar

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:18000").rstrip("/")
ADMIN_PW = sys.argv[2] if len(sys.argv) > 2 else "123"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, "init_data.json")))

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(path, obj):
    body = json.dumps(obj).encode()
    req = urllib.request.Request(BASE + path, data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        r = opener.open(req, timeout=30)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"status": "error", "msg": f"HTTP {e.code}: {e.read().decode()[:120]}"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


def login():
    res = call("/api/login", {"application": "app-built-in", "organization": "built-in",
                              "username": "admin", "password": ADMIN_PW,
                              "type": "login", "signinMethod": "Password"})
    if res.get("status") != "ok":
        print("FATAL: admin login failed:", res.get("msg")); sys.exit(1)
    print("admin login: ok")


def seed(kind, path, items, label):
    for it in items:
        it.setdefault("createdTime", "2026-01-01T00:00:00Z")
        res = call(path, it)
        name = it.get("name", "?")
        st, msg = res.get("status"), (res.get("msg") or "")
        ok = st == "ok" or "exist" in msg.lower() or "duplicate" in msg.lower()
        print(f"  {kind} {name}: {'ok' if ok else 'ERR'} {msg if not ok else ''}".rstrip())


def rebrand_builtin():
    # Point the admin console (built-in org + app) at the eUnionX/Gandalf brand.
    logo = "http://localhost:18000/eunionx-logo.svg"
    theme = DATA["organizations"][0]["themeData"]
    org = call("/api/get-organization", {}) if False else None  # placeholder
    # get + patch built-in org
    try:
        r = opener.open(BASE + "/api/get-organization?id=admin/built-in", timeout=30)
        bo = json.loads(r.read().decode()).get("data")
        if bo:
            # org logo/favicon columns are varchar(200) - keep them short; the
            # brand colour + displayName carry the rebrand, app logos show the mark.
            bo.update({"displayName": "eUnionX", "logo": logo, "favicon": logo, "themeData": theme})
            print("  rebrand built-in org:", call("/api/update-organization?id=admin/built-in", bo).get("status"))
    except Exception as e:
        print("  rebrand built-in org: skip", e)
    try:
        r = opener.open(BASE + "/api/get-application?id=admin/app-built-in", timeout=30)
        ba = json.loads(r.read().decode()).get("data")
        if ba:
            ba.update({"displayName": "Gandalf - eUnionX access gate", "logo": logo,
                       "themeData": theme, "formCss": "",
                       "footerHtml": DATA["applications"][0].get("footerHtml", "")})
            print("  rebrand built-in app:", call("/api/update-application?id=admin/app-built-in", ba).get("status"))
    except Exception as e:
        print("  rebrand built-in app: skip", e)


def main():
    login()
    print("seeding:")
    seed("org", "/api/add-organization", DATA.get("organizations", []), "org")
    seed("cert", "/api/add-cert", DATA.get("certs", []), "cert")
    seed("app", "/api/add-application", DATA.get("applications", []), "app")
    seed("user", "/api/add-user", DATA.get("users", []), "user")
    seed("role", "/api/add-role", DATA.get("roles", []), "role")
    print("rebranding admin console:")
    rebrand_builtin()
    print("done.")


if __name__ == "__main__":
    main()
