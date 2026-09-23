# Deploying CSW on-prem

This covers running CSW on one internal Linux server with Docker, behind
HTTPS with a cert from your org's internal CA, with sign-in via Azure AD
(Entra ID) SAML SSO. It's the setup this repo is built for — SQLite +
local file storage on one persistent volume, one `api` container and one
`web` (Caddy) container in front of it.

This is sized for a small team (roughly <10 concurrent users). If you
outgrow that, the main thing to change is swapping SQLite for Postgres
(see `api/app/db.py` — it's one `DATABASE_URL`) and moving file storage
off local disk; nothing else in this guide changes.

## Prerequisites

- A Linux host (VM or bare metal) with Docker + Docker Compose v2 installed.
- An internal DNS name for the app (e.g. `csw.internal.yourcompany.com`)
  resolving to that host, reachable from your users' network.
- A TLS cert + private key for that DNS name, issued by your org's
  internal CA.
- (For SSO) An Azure AD (Entra ID) admin who can create an Enterprise
  Application and tell you three Azure AD group Object IDs.

## 1. Get the code onto the server

```bash
git clone https://github.com/dineshjangid/ScoreX.git csw
cd csw
cp .env.example .env
```

## 2. Fill in `.env`

At minimum, set `SITE_ADDRESS`, `TLS_CERT_PATH`, and `TLS_KEY_PATH` (paths
on the *host*, to the cert/key from your internal CA). Leave every
`SAML_*` variable blank for now — the app runs fine with local
username+password accounts (create one via the login page's "Register"
tab) with SSO off. Add SAML once you're ready for step 4.

## 3. Build and run

```bash
docker compose up -d --build
```

Check it's up:

```bash
docker compose logs -f
curl -k https://<SITE_ADDRESS>/api/health   # {"status": "ok"}
```

Open `https://<SITE_ADDRESS>` in a browser and register the first account
(pick any role — roles are attribution labels on the audit log here, not
access restrictions; everyone can see every project).

## 4. (Optional) Turn on Azure AD SSO

**a. Get the SP metadata to your Azure AD admin.** Once `SITE_ADDRESS`
is live, the SP metadata is served at:

```
https://<SITE_ADDRESS>/api/auth/saml/metadata
```

That 404s until `SAML_IDP_ENTITY_ID` is set in `.env` — that's expected;
for step (a) your admin only needs the two URLs below, not that endpoint
yet.

**b. Ask your Azure AD admin to create an Enterprise Application** (SAML
type) with:

- **Identifier (Entity ID)**: `https://<SITE_ADDRESS>/api/auth/saml/metadata`
- **Reply URL (ACS URL)**: `https://<SITE_ADDRESS>/api/auth/saml/acs`
- **Group claims**: enabled, emitting **Group ID** (not name — names can
  be renamed later, IDs can't) for the groups assigned to the app.

**c. Get from your admin, and put in `.env`:**

- `SAML_IDP_ENTITY_ID` — from the app's Federation Metadata XML
  (`entityID` on `<EntityDescriptor>`).
- `SAML_IDP_SSO_URL` — the "Login URL" shown on the Azure AD app's SAML
  setup page.
- `SAML_IDP_X509_CERT` — the base64 certificate value from "SAML
  Certificates" (the raw base64 body, no `-----BEGIN CERTIFICATE-----`
  header/footer, no line breaks — one long string).
- The **Object ID** of three Azure AD groups (create them if they don't
  exist yet, and add your users to them) → `SAML_GROUP_ANALYST_ID`,
  `SAML_GROUP_VALIDATOR_ID`, `SAML_GROUP_APPROVER_ID`. Someone in more
  than one gets the highest-privilege matching role (approver >
  validator > analyst). Someone in none of the three is rejected at
  login unless you set `SAML_DEFAULT_ROLE`.

**d. Restart the app** so it picks up the new `.env` values:

```bash
docker compose up -d
```

The login page now shows a "Sign in with Microsoft" button above the
local-account form (which stays available as a fallback).

## Backups

Everything CSW stores — the SQLite database, uploaded datasets, batch
files, persisted ML final-model files — lives in the `csw_data` Docker
volume (mounted at `/data` in the `api` container). Back that up on a
schedule appropriate for how much rebuilding a lost project would cost
you, e.g.:

```bash
docker run --rm -v csw_data:/data -v /backup/path:/backup alpine \
  tar czf /backup/csw-data-$(date +%F).tar.gz -C /data .
```

There's no redundancy built in beyond this — one VM going down loses
everything since the last backup. That's a reasonable trade for a small
internal team; revisit it if uptime requirements grow.

## Updating

```bash
git pull
docker compose up -d --build
```

Your data volume is untouched by rebuilds.
