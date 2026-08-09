"""Chimera Creator API."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
    await _load_custom_parts()
    from .services import ai
    if not ai.ai_enabled():
        logging.getLogger("chimera").warning(
            "AI DISABLED — no OPEN_AI_API_KEY found (looked in %s). Creatures "
            "will be STUB records with no hero renders. This is never what you "
            "want outside tests.", "repo-root .env / environment",
        )
    await _sweep_orphans()
    await _seed_starter_crew()
    yield


async def _load_custom_parts() -> None:
    """Merge Henry's summoned parts (custom_parts table) into the live library
    so they show in the picker forever after. Best-effort, never blocks boot."""
    from .db import session_factory
    from .services import summon as summon_svc

    try:
        async with session_factory()() as db:
            count = await summon_svc.load_custom_parts(db)
        if count:
            logging.getLogger("chimera").info("library: +%d summoned parts", count)
    except Exception:
        logging.getLogger("chimera").exception("loading summoned parts failed — continuing")


async def _sweep_orphans() -> None:
    """In-flight generation tasks die with the process; on boot, any row still
    generating/pending is an orphan. Mark it failed so the UI's retry button
    can rescue it instead of polling a ghost forever."""
    from sqlalchemy import update

    from .db import session_factory
    from .models import Creature, CustomPart, ImageStatus, RecordStatus

    async with session_factory()() as db:
        rec = await db.execute(
            update(Creature)
            .where(Creature.record_status == RecordStatus.generating)
            .values(record_status=RecordStatus.failed, image_status=ImageStatus.failed)
        )
        img = await db.execute(
            update(Creature)
            .where(Creature.record_status == RecordStatus.complete,
                   Creature.image_status == ImageStatus.pending)
            .values(image_status=ImageStatus.failed)
        )
        # Summoned-part portraits share the same orphan fate on restart.
        parts = await db.execute(
            update(CustomPart)
            .where(CustomPart.portrait_status == ImageStatus.pending)
            .values(portrait_status=ImageStatus.failed)
        )
        await db.commit()
        if rec.rowcount or img.rowcount or parts.rowcount:
            logging.getLogger("chimera").info(
                "orphan sweep: %d records, %d images, %d part portraits marked failed",
                rec.rowcount, img.rowcount, parts.rowcount)


async def _seed_starter_crew() -> None:
    """First run only: an empty creatures table gets the committed starter
    crew (data/seed) so the Codex and one full bracket exist immediately.
    Seeding is best-effort — a broken or missing pack never blocks boot."""
    from .db import session_factory
    from .services.seed import seed_if_empty

    try:
        async with session_factory()() as db:
            await seed_if_empty(db)
    except Exception:
        logging.getLogger("chimera").exception("starter-crew seeding failed — continuing")


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

_media = get_settings().media_dir
_media.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=_media), name="media")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": get_settings().env}
