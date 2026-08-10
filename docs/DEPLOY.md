# Deploying Chimera Creator to Railway

One player, one service, one origin. FastAPI serves `/api/*`, `/media/*` (a
persistent volume) and the built React SPA out of a single container, so there
is no CORS to configure in production and no second service to keep in step.

```
GitHub main ──push──▶ Railway build (root Dockerfile)
                        stage 1  node:22-alpine   npm ci && npm run build  ─▶ dist/
                        stage 2  python:3.12-slim backend + dist ─▶ /app/static
                              │
                              ▼
                     container boot: alembic upgrade head ─▶ uvicorn :$PORT
                              │
              ┌───────────────┼────────────────┐
        Postgres (managed)    │          Volume /data
                              ▼
                       /healthz (deploy gate)
```

---

## 1. Railway objects to create

| Object | Setting |
|---|---|
| Service | Source: this GitHub repo, branch `main`. Builder: Dockerfile (`railway.toml` pins it). |
| Postgres | Railway managed Postgres plugin, in the same project. |
| Volume | Attached to the app service, **mount path `/data`**. Media then lives at `/data/media`. |
| Domain | Generate a Railway domain on the app service; see §9 for the custom one. |

The service must be the **repo root**, not `backend/` or `frontend/` — the root
`Dockerfile` builds both halves.

## 2. Environment variables

Set these on the **app service**:

| Variable | Value | Why |
|---|---|---|
| `OPEN_AI_API_KEY` | *(the real key)* | gpt-5.1 records + gpt-image-1.5 renders. Without it every creature is a stub with no art. |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Railway variable reference to the Postgres service. `config.py` rewrites `postgresql://` to `postgresql+asyncpg://` itself. |
| `CHIMERA_ENV` | `prod` | |
| `CHIMERA_PLAYER` | `Henry` | |
| `CHIMERA_MEDIA_DIR` | `/data/media` | The volume. Already the image default — set it explicitly anyway so it is visible in the dashboard. |
| `CHIMERA_PIN` | *(4 digits)* | The lab door. Arms the PIN gate: every `/api/*` + `/media/*` request 401s without the session cookie (login + health exempt). **Unset = gate disabled** — the app is open to the internet and its OpenAI-backed endpoints are hammerable. Keep it 4 digits: the gate screen auto-submits at exactly 4. |
| `CHIMERA_SESSION_SECRET` | `openssl rand -hex 32` | Signs the 180-day session cookie. Optional (falls back to a PIN-derived key) but recommended; rotating it logs every device out. |

**Do not set** — the image already pins them, and overriding will break things:
`CHIMERA_STATIC_DIR` (`/app/static`), `CHIMERA_DATA_DIR` (`/app/data`).
**Do not set** `PORT` — Railway injects it and the entrypoint reads it.
`CHIMERA_CORS_ORIGINS` is irrelevant in prod (same origin) and can be left alone.

> `DATABASE_URL` is not optional. If it is missing the app silently falls back
> to a SQLite file inside the container, which vanishes on every deploy and
> would look exactly like "Henry's creatures disappeared".

**`.env` is gitignored and must stay that way.** It is excluded from the Docker
build context by `.dockerignore` and is never copied into an image layer. Secrets
live only in Railway's variable store.

## 3. First deploy — order of operations

1. Create the Postgres plugin **first**, so `${{Postgres.DATABASE_URL}}` resolves.
2. Create the volume on the app service at `/data` **before** the first deploy —
   attaching a volume later triggers a redeploy anyway.
3. Set every variable from §2.
4. Deploy (push to `main`, or "Deploy" in the dashboard).
5. Watch the build+deploy logs for, in order:
   ```
   [entrypoint] alembic upgrade head
   INFO  [alembic.runtime.migration] Running upgrade  -> d71354bd48b7, initial schema
   [entrypoint] starting uvicorn on 0.0.0.0:8080
   INFO:chimera:serving SPA from /app/static
   INFO:     Application startup complete.
   ```
6. `curl https://<domain>/healthz` → `{"ok":true}`; `/readyz` → `{"ok":true,"db":"ok"}`.

At this point the app works but contains the **starter crew** — 8 seeded
chimeras the app inserts into any empty database on boot. That is expected, and
step 4 of the bootstrap below replaces them with Henry's real game.

## 4. Data bootstrap (one time, moves Henry's existing game up)

His ~30 creatures, ~100 cached battles and tournament history are in the local
SQLite file; his art (~17MB of WebP) is in `media/`. Creature **ids are load-bearing**
— `media/creatures/<id>.webp`, tournament brackets and `battles.canonical_key`
all reference them — so the migration preserves primary keys exactly and then
fast-forwards the Postgres sequences past them.

**Stop the local game first** so nothing is mid-write, and take a copy of the
SQLite file to migrate from:

```bash
cp ./chimera.db ./chimera-bootstrap.db
```

**(1) Deploy** — done in §3.
**(2) `alembic upgrade head`** — ran automatically on boot.

**(3) Copy the database — from inside the container.** The Postgres service
has **no `DATABASE_PUBLIC_URL`**: it exposes only the private
`postgres.railway.internal` hostname, which does not resolve from a laptop.
Rather than open a public TCP proxy on the database for a one-time job, ship
the SQLite file up to the volume and run the migration next to Postgres, over
the private network:

The image does **not** carry `scripts/` (it ships only the backend app), so the
migration script rides up on the volume next to the database file. Its only
`__file__`-relative behavior is a `sys.path` insert that resolves harmlessly
from `/data`; the `app` package imports come from the `cd /app` working
directory. Note `--volume` goes on `files`, before the subcommand — without it
a non-interactive shell errors out instead of prompting.

```bash
railway link                                    # select the project/service
railway volume files --volume chimera-volume \
    upload ./chimera-bootstrap.db /data/chimera-bootstrap.db --overwrite
railway volume files --volume chimera-volume \
    upload ./scripts/migrate_to_railway.py /data/migrate_to_railway.py --overwrite

# look first — prints per-table row counts and the sequence values it will set
railway ssh --service chimera \
    'cd /app && python /data/migrate_to_railway.py \
        --sqlite /data/chimera-bootstrap.db --target "$DATABASE_URL" --dry-run'

# the real run. --force is expected here: it deletes the auto-seeded starter
# crew before inserting Henry's rows. Without it the script refuses to touch a
# non-empty database.
railway ssh --service chimera \
    'cd /app && python /data/migrate_to_railway.py \
        --sqlite /data/chimera-bootstrap.db --target "$DATABASE_URL" --force'
```

`$DATABASE_URL` is already in the container's environment, so the connection
string never lands in a laptop shell or its history. Delete both uploaded
files afterwards:
`railway ssh --service chimera 'rm /data/chimera-bootstrap.db /data/migrate_to_railway.py'`
(the CLI's `volume files delete` wants an interactive confirm; `ssh` + `rm`
does not).

Expected tail:

```
sequence public.creatures_id_seq -> next id = 32
...
verified row counts match source for every table.
```

The script is re-runnable: `--force` wipes and re-inserts, landing on the same
ids every time.

**(4) Upload the media** with the Railway CLI's native volume file support
(no upload endpoint in the app — a kid's game does not need an auth surface):

```bash
railway link                                   # select the project/service
railway volume files --volume chimera-volume upload ./media /data --overwrite
railway volume files --volume chimera-volume list /data/media/creatures | head
```

The destination is `/data`, not `/data/media`: the CLI nests the uploaded
directory *under* the destination, so `./media -> /data` lands at
`/data/media/...` while `./media -> /data/media` lands at the wrong
`/data/media/media/...` (verified on the real volume, CLI 5.35). Sanity-check
the listing shows `1.webp`, `1_thumb.webp`, … directly under
`/data/media/creatures`; if they nested, fix in place with
`railway volume files --volume chimera-volume rename /data/media/media/creatures /data/media/creatures`
(same for `parts/`) rather than re-uploading 18 MB.

**(5) Restart the service.** This is not optional: the app loads Henry's
summoned custom parts into the in-memory source library **at boot**, so the 3
custom parts just inserted will not appear in the fusion picker until the
process restarts. Redeploy or restart from the dashboard.

**(6) Verify in a browser**, not just with curl:
- the Codex shows ~26 creatures with hero art (proves DB **and** volume)
- open a past tournament — the bracket replays instantly from the battle cache
- the Hall of Champions lists his champions
- create one new creature: it must be saved with id **32** or higher. An
  "duplicate key value violates unique constraint" error here means the sequence
  reset did not happen — re-run step 3.

## 5. Deploy downtime — the honest version

**This service cannot do zero-downtime deploys.** Railway only overlaps the old
and new containers for services *without* a mounted volume; a volume can be
attached to exactly one running container, so a deploy here is stop-old →
start-new. Expect roughly 10–40 seconds of 502s per deploy (image pull +
`alembic upgrade head` + uvicorn boot).

For an audience of one 8-year-old this is the right trade — a volume is far
simpler than object storage, and he is not playing during a deploy. Just do not
describe it as seamless, and do not deploy mid-tournament.

`healthcheckPath = "/healthz"` still matters: Railway will not route traffic to
the new container until it answers, so a container that fails to boot leaves the
previous deployment in place instead of taking the game down.

## 6. Rolling back

**Code:** Railway dashboard → service → Deployments → "Redeploy" on the last
good deployment. This rebuilds nothing and swaps back in ~30s.

**Schema:** rolling back code does **not** roll back a migration. The initial
migration is additive-only, so any rollback today is safe. Once there is a
second migration, undo it explicitly before redeploying older code:

```bash
DATABASE_URL="$PG" .venv/bin/alembic -c backend/alembic.ini downgrade -1
```

**Data:** Railway Postgres takes automatic backups — restore from the Postgres
service's Backups tab. Also keep `chimera-bootstrap.db` and a copy of `media/`
on the laptop; between them the entire game can be rebuilt from scratch with §4.

**Media:** the volume survives deploys and rollbacks. It does *not* survive
deleting the service. `railway volume files download` before any destructive
change to the service.

## 7. Local rehearsal (what was actually tested)

```bash
docker run -d --name pg -e POSTGRES_USER=chimera -e POSTGRES_PASSWORD=chimera \
    -e POSTGRES_DB=chimera -p 55432:5432 postgres:16-alpine

docker build -t chimera .

docker run --rm -p 8099:8099 -e PORT=8099 -e CHIMERA_ENV=prod \
    -e DATABASE_URL="postgresql://chimera:chimera@host.docker.internal:55432/chimera" \
    -v "$PWD/media:/data/media" chimera
```

Then `curl localhost:8099/healthz`, `/readyz`, `/api/library`, `/api/creatures`
and open `http://localhost:8099/`.

Prod is the canonical environment now (the pre-deploy local playtest on ports
8010/5175 was retired 2026-08-09). QA runs against the deployed site; for
frontend work with real data and no local backend, run the Vite dev server
with `VITE_PROXY_TARGET=https://chimera-production-4a3c.up.railway.app` and
stick to read-only browsing — every click that POSTs lands in Henry's real
Codex.

## 8. Gotchas worth remembering

- **The build context is mostly art**: `frontend/public/assets` is committed
  and required by the Vite build. It is WebP now — 49MB, down from 217MB of PNG
  — which is the single biggest lever on build time. `.dockerignore` keeps
  `media/`, `qa/`, `research/`, `scripts/raw/`, `.venv/` and `node_modules/` out.
- **The container runs as root.** Railway volumes are root-owned; a non-root
  user would need a chown step at boot for no benefit here.
- **Migrations run in the entrypoint, not in the app lifespan.** A failed
  migration therefore fails the deploy loudly instead of half-starting the app
  against a stale schema.
- **SQLite dev is unchanged.** `create_all` still stands the schema up locally;
  alembic is the Postgres path only. CI asserts the two agree (`alembic check`).

## 9. The custom domain (`chimera.uptownnickbrown.com`)

Railway hands out a free `*.up.railway.app` domain and terminates TLS on it.
A custom domain is two halves — Railway claims the name and provisions the
certificate, the registrar points DNS at it:

```bash
railway domain --service chimera chimera.uptownnickbrown.com
```

That prints a CNAME target (`<something>.up.railway.app`). The registrar is
**Hover**, which has no public API, no CLI and no MCP server, so this record is
added by hand in their control panel — `uptownnickbrown.com` → DNS → Add:

| Type | Hostname | Value |
|---|---|---|
| CNAME | `chimera` | *(the target Railway printed)* |

Railway polls DNS, then issues the certificate — usually minutes, up to about
an hour if Hover's TTL is long. `railway domain --json` shows the status.

A subdomain is the easy case. The apex `uptownnickbrown.com` could not be
CNAME'd this way (it already carries the main site's records), which is why the
game lives on a subdomain.

Nothing in the app needs to change: `CHIMERA_CORS_ORIGINS` is irrelevant here
because the API and the SPA are served from the same origin, whatever that
origin is called. The old `*.up.railway.app` URL keeps working alongside it.
