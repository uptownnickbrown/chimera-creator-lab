"""Chimera Creator API."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import creatures, library, profile, tournaments
from .config import get_settings
from .db import create_all
from .services import library as library_svc

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev/SQLite convenience: stand the schema up in place. Postgres gets
    # `alembic upgrade head` as a release step (see alembic/).
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        await create_all()
    # Authored content is optional at boot — load_library logs and shrugs.
    library_svc.load_library()
    yield


app = FastAPI(title="Chimera Creator API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(creatures.router)
app.include_router(tournaments.router)
app.include_router(library.router)
app.include_router(profile.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": get_settings().env}
