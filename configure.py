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
import json, os, sys, urllib.request, urllib.error, urllib.parse, http.cookiejar

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:18000").rstrip("/")
# Target Casdoor admin password. On a fresh install the admin password is `123`;
# login() logs in with that and rotates it to ADMIN_PW so the api (which fails
# closed on the dev default under ENV=prod) can authenticate.
ADMIN_PW = sys.argv[2] if len(sys.argv) > 2 else "123"
# The `eunionx-mobile` OIDC client secret the api uses for the OTP token grant.
# When set, it is enforced onto the seeded app (add-application no-ops on an
# already-seeded DB, so an existing app keeps its old secret without this).
OTP_CLIENT_SECRET = os.environ.get("GANDALF_OTP_CLIENT_SECRET", "")
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


def call_form(path, fields):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(BASE + path, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        r = opener.open(req, timeout=30)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"status": "error", "msg": f"HTTP {e.code}: {e.read().decode()[:120]}"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


def login_with(pw):
    res = call("/api/login", {"application": "app-built-in", "organization": "built-in",
                              "username": "admin", "password": pw,
                              "type": "login", "signinMethod": "Password"})
    return res.get("status") == "ok"


def rotate_admin_password(old_pw, new_pw):
    res = call_form("/api/set-password", {"userOwner": "built-in", "userName": "admin",
                                          "oldPassword": old_pw, "newPassword": new_pw})
    if res.get("status") != "ok":
        print("FATAL: admin password rotation failed:", res.get("msg")); sys.exit(1)
    print("  rotate admin password: ok")


def login():
    # Re-run / already-rotated case: the target password already works.
    if login_with(ADMIN_PW):
        print("admin login: ok"); return
    # Fresh install: Casdoor's admin is still `123`. Log in and rotate to ADMIN_PW.
    if ADMIN_PW != "123" and login_with("123"):
        print("admin login: ok (fresh install)")
        rotate_admin_password("123", ADMIN_PW)
        return
    print("FATAL: admin login failed (tried target password and fresh-install 123)")
    sys.exit(1)


def enforce_mobile_secret():
    # add-application no-ops when the app already exists, so an already-seeded DB
    # keeps its old client secret. Enforce the configured one onto the live app.
    if not OTP_CLIENT_SECRET:
        return
    try:
        r = opener.open(BASE + "/api/get-application?id=admin/eunionx-mobile", timeout=30)
        app = json.loads(r.read().decode()).get("data")
    except Exception as e:
        print("  enforce eunionx-mobile secret: skip", e); return
    if not app:
        print("  enforce eunionx-mobile secret: app not found"); return
    if app.get("clientSecret") == OTP_CLIENT_SECRET:
        print("  enforce eunionx-mobile secret: already current"); return
    app["clientSecret"] = OTP_CLIENT_SECRET
    print("  enforce eunionx-mobile secret:",
          call("/api/update-application?id=admin/eunionx-mobile", app).get("status"))


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
    print("enforcing app secrets:")
    enforce_mobile_secret()
    print("rebranding admin console:")
    rebrand_builtin()
    print("done.")


if __name__ == "__main__":
    main()
