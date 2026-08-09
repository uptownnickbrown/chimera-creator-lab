#!/bin/sh
# Container boot: migrate, then serve. Migrations run HERE and not in the app
# lifespan so a bad migration fails the deploy loudly (and Railway keeps the
# previous container) instead of half-starting an app against a stale schema.
set -e

cd /app

# The Railway volume is mounted at /data; the media subdir may not exist yet on
# a fresh volume. StaticFiles refuses to mount a missing directory.
mkdir -p "${CHIMERA_MEDIA_DIR:-/data/media}"

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

# Anything passed as a command wins (Railway custom start command, `docker run
# ... sh` for a poke around). With no arguments, serve the app — PORT is
# injected by Railway and defaults to 8000 locally.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "[entrypoint] starting uvicorn on 0.0.0.0:${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
