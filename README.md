# Chimera Creator

A creature-fusion game built for exactly one player: an eight-year-old named
Henry. Pick four source creatures — mythic, extinct, living, or one you just
made up — and the lab fuses them into a brand-new chimera with an AI-written
record and a movie-monster render. Chimeras live forever in the Codex and
fight in eight-creature tournament brackets where the game is predicting the
winner.

Live at **https://chimera.uptownnickbrown.com** (kid-gated behind an avatar
profile).

## How it works

- **Creation** is staged for suspense: `gpt-5.1` streams the creature record
  (name first, ~2s in) while `gpt-image-1.5` paints a transparent-background
  hero render (~50s) behind the fusion-chamber animation.
- **The part library is hybrid**: ~95 curated parts with pregenerated
  portraits, plus "Summon New Creature" — type anything and it becomes a
  permanent library part, generated on the fly.
- **Battles are fully deterministic**: same matchup + same environment = same
  winner, every time. Variety comes from the environments.
- **OpenAI-only, quality over cost.** Audience of one; there is no scale to
  worry about. See `research/bakeoff/` for the model-selection evidence.

## Stack

FastAPI + Postgres (SQLite in dev) behind `/api` and `/media`; React 18 +
TypeScript + Vite SPA served as static files by the same app. One Docker
container on Railway with a volume for generated media; pregenerated WebP UI
art is committed under `frontend/public/assets`. Pushing to `main` runs CI
and, on green, auto-deploys to production.

```
backend/    FastAPI app, SQLAlchemy models, alembic migrations
frontend/   React + Vite SPA (hash routing), committed asset library
docs/       the five documents below
scripts/    asset pipeline, QA sweeps, one-time migration tooling
research/   model bakeoff results that locked the AI roster
```

## Docs

| Doc | What it covers |
| --- | --- |
| `docs/ARCHITECTURE.md` | System shape, data model, generation pipeline |
| `docs/AI_CONTRACTS.md` | Prompts, schemas, and model contracts |
| `docs/UI_STANDARD.md` | Visual system: palette, type, per-screen composition |
| `docs/ASSET_WISHLIST.md` | Pregenerated art inventory |
| `docs/DEPLOY.md` | Railway deploy, migrations, backups, rollback |

## Development

```bash
# backend (SQLite, schema via create_all — no migration step needed locally)
.venv/bin/uvicorn app.main:app --app-dir backend            # port 8000

# frontend (proxies /api and /media to localhost:8000)
npm --prefix frontend run dev
```

To QA the frontend against real production data without a local backend,
point the dev proxy at prod and stick to read-only browsing:

```bash
VITE_PROXY_TARGET=https://chimera-production-4a3c.up.railway.app \
  npm --prefix frontend run dev
```

Secrets live in an untracked `.env`. The OpenAI key is read from
`OPEN_AI_API_KEY` — the nonstandard spelling is load-bearing; Railway has
exactly that name set.
