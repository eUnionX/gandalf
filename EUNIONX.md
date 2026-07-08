# Gandalf 🧙‍♂️ - eUnionX's IAM (a fork of Casdoor)

> "You shall not pass." - the identity and access gate in front of every eUnionX
> surface: the trader web app, the warroom, and mobile.

This repository is **eUnionX's own fork of [Casdoor](https://github.com/casdoor/casdoor)**,
an open-source Identity and Access Management (IAM) / single-sign-on platform. We own
the full source here (`eUnionX/gandalf`) so we have complete control: any change we need,
from branding to behaviour, is ours to make. The GitHub fork keeps its link to upstream,
so we can pull Casdoor's security fixes and features with `git` and merge them on our terms.

## What eUnionX changed on top of upstream Casdoor
Kept deliberately small so upstream merges stay easy:
- **`conf/app.conf`** - eUnionX server config: `appname = gandalf`, Postgres storage
  (a dedicated `gandalf` database), and the public `origin` `http://localhost:18000`.
- **`web/public/index.html`** - browser tab title "Gandalf - eUnionX access gate",
  favicon, and description point at eUnionX.
- **`web/public/eunionx-logo.svg`** - the eUnionX X-mark, served at `/eunionx-logo.svg`
  and used as the login/console logo.
- **`init_data.json`** - the eUnionX seed: the `eunionx` organisation, a JWT signing
  cert, the OIDC applications for the trader web / warroom / mobile, users, and roles,
  with the turquoise brand theme.
- **`configure.py`** - an idempotent seeder that applies `init_data.json` through
  Casdoor's REST API and rebrands the admin console. Casdoor only imports
  `init_data.json` on a first-ever empty-DB boot, so this makes seeding reliable on
  every start.
- **`eunionx/architecture.md`** - how Gandalf gates the three clients (OIDC flow).

## Build and run
Gandalf runs as part of the eUnionX stack (`docker compose up -d` / `make up`), which
builds this fork from source and brings it up on **http://localhost:18000**, backed by
a dedicated `gandalf` database on the shared Postgres.

Build from source directly (the `STANDARD` target is the server image):
```
docker build --target STANDARD -t eunionx/gandalf:dev .
```
Then seed + rebrand (idempotent):
```
python3 configure.py http://localhost:18000 123
```

## Dev credentials (local only)
| Role | Username | Password |
|---|---|---|
| Super admin | `gandalf` | `Gandalf@eunionx1` |
| Warroom operator | `operator` | `Operator@eunionx1` |
| Demo trader | `trader` | `Trader@eunionx1` |
| Upstream default | `admin` | `123` |

**Local development only. Never use these values, or the committed dev signing cert, in
any shared or production environment.**

## Keeping up with upstream
```
git remote add upstream https://github.com/casdoor/casdoor.git
git fetch upstream && git merge upstream/master   # resolve, keeping the eUnionX changes above
```

The upstream Casdoor README follows below.
