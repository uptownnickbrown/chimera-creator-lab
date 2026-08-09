# Chimera Creator — single-image production build (Railway).
#
# One service, one origin: FastAPI serves /api/*, /media/* (persistent volume)
# and the built React SPA. Same origin means no CORS in prod and no second
# service to keep in sync.
#
#   stage "web"  node:22-alpine   -> frontend/dist  (Vite build, @fontsource bundled)
#   stage final  python:3.12-slim -> backend + dist copied to /app/static
#
# Build locally with:  docker build -t chimera .

# ---------------------------------------------------------------- frontend ---
FROM node:22-alpine AS web

WORKDIR /build

# Lockfile-only layer: dependency installs are cached until the lockfile moves.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Sources + public/ (the ~230MB pregenerated art library is part of the app).
COPY frontend/ ./

# `npm run build` is `tsc -b && vite build`, so this also typechecks.
RUN npm run build


# ----------------------------------------------------------------- runtime ---
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # config.py derives its defaults from the repo root, which does not exist
    # in this layout — every path is pinned explicitly instead.
    CHIMERA_DATA_DIR=/app/data \
    CHIMERA_MEDIA_DIR=/data/media \
    CHIMERA_STATIC_DIR=/app/static \
    PORT=8000

WORKDIR /app

# Runtime dependencies only (no [dev] extra: no pytest, no ruff).
# asyncpg / pillow / uvloop all ship cp312 manylinux wheels, so no toolchain.
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir -e .

# Schema migrations run from the entrypoint before uvicorn binds the port.
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic

# Authored content: source creatures, environments, starter-crew seed pack.
COPY data ./data

# The built SPA. Served by app.main when CHIMERA_STATIC_DIR/index.html exists.
COPY --from=web /build/dist ./static

COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
