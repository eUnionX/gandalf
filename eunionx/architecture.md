# Gandalf architecture

Gandalf is the eUnionX access gate: one IAM in front of every client, speaking
OpenID Connect (OIDC). It is a branded fork of Casdoor.

## Where it sits
```
   Trader web (:3000)     Warroom (:3001)      Mobile
        \                     |                  /
         \  1. redirect to sign in (OIDC)       /
          \____________________|_______________/
                               v
                    ┌──────────────────────┐
                    │  Gandalf  (:18000)    │   branded Casdoor
                    │  login · consent      │
                    │  users · roles · orgs │
                    │  tokens · audit       │
                    └──────────┬────────────┘
                               │ stores in
                    ┌──────────▼────────────┐
                    │ Postgres db "gandalf"  │  (shared PG, dedicated DB)
                    └────────────────────────┘
                               │ 2. issues signed JWT (RS256, per-instance cert)
                               v
                    the client calls the eUnionX api with the token;
                    the api trusts Gandalf as the identity provider.
```

## The login flow (Authorization Code + PKCE)
1. A user opens a client (e.g. the trader web). The client has no session, so it
   redirects the browser to Gandalf's `/login/oauth/authorize` with its `clientId`,
   `redirect_uri`, `scope`, and a PKCE challenge.
2. Gandalf shows the eUnionX-branded sign-in page. The user authenticates
   (password, one-time code, WebAuthn, ...).
3. Gandalf redirects back to the client's `redirect_uri` with a short-lived
   `code`.
4. The client exchanges the `code` at `/api/login/oauth/access_token` for a signed
   **JWT** (access token + id token) and a refresh token.
5. The client presents that JWT to the eUnionX `api`. The api verifies the
   signature against Gandalf's JWKS (`/.well-known/jwks`) and reads the user's
   identity and roles from the claims.

Discovery document: `GET /.well-known/openid-configuration`.

## Clients (seeded OIDC applications)
| Client | clientId | Redirect URI | Notes |
|---|---|---|---|
| Trader web | `eunionx-web` | `http://localhost:3000/callback` | public SPA + PKCE |
| Warroom | `eunionx-warroom` | `http://localhost:3001/callback` | operator console |
| Mobile | `eunionx-mobile` | `eunionx://auth/callback` | native deep link |

Each has a `clientSecret` (dev: `<clientId>-secret-dev`) for the confidential
code exchange. All three sign in against the `eunionx` organisation and share the
`cert-gandalf` JWT signing certificate.

## Client integration
**Trader web: WIRED (done).** The web app (`web/src/lib/oidc.ts` + `App.tsx`) signs in
through Gandalf via Authorization-Code + PKCE: "Sign in with Gandalf" redirects to the
authorize endpoint; `/callback` exchanges the code for tokens in the browser (Gandalf
allows CORS from `http://localhost:3000`); the eUnionX session is established from the
token's identity claim (`accountId = email`). Verified end to end: the trader signs in
at the gate and lands in the terminal as `trader@eunionx.com`.

**Warroom and mobile: same pattern, pending.** Per remaining client:
- add an OIDC client library (e.g. `oidc-client-ts` on web, `AppAuth` on mobile);
- configure issuer `http://localhost:18000`, the `clientId`, and the `redirect_uri`
  above;
- on app load, if there is no valid token, redirect to Gandalf; handle the
  callback; store the token; attach it as `Authorization: Bearer` to api calls;
- the eUnionX `api` validates the JWT against Gandalf's JWKS (the deeper backend step).

This replaces each app's local login screen with the shared Gandalf gate. The
eUnionX onboarding/OTP journey continues to live in the `api`; Gandalf owns
authentication and session, the `api` owns the trader lifecycle and provisioning.

## Storage
A dedicated `gandalf` database on the shared eUnionX Postgres (created by the
`gandalf-init` step). Keeping it in its own database keeps Gandalf modular and
independently backup-able while reusing one database engine.

## Branding
Driven by data, not source patches:
- **Login + admin pages**: each application's `logo` (the eUnionX X-mark, served by
  Gandalf at `/eunionx-logo.svg`), `themeData.colorPrimary` = `#2DD4BF` (the eUnionX
  turquoise), and a footer ("You shall not pass without identity").
- **Browser tab / metadata**: the Dockerfile rewrites the built frontend's title to
  "Gandalf - eUnionX access gate" and points the favicon at the eUnionX mark.
- Green/red are never used for the brand (eUnionX design rule); turquoise is the
  single brand colour.

## Seeding (why `configure.py`, not just `init_data.json`)
Casdoor only imports `init_data.json` on a first-ever, empty-database boot, which is
brittle across restarts. `configure.py` seeds the same objects through Casdoor's
REST API as the admin and is idempotent, so the stack always converges to the
intended state. `init_data.json` remains the single declarative source of truth for
what those objects are; `configure.py` reads it.

## Security notes (local dev posture)
- The signing cert and all passwords in this repo are **local-dev only**. Production
  must generate its own cert (a Casdoor cert per environment) and real credentials,
  and must run Gandalf over TLS with production redirect URIs and secrets.
- No external IdP or secret is required to run locally; everything is self-contained.
