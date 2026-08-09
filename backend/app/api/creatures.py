"""Creature creation and the Codex (spec §7 MAKE/REVEAL/COLLECT, §14)."""
from __future__ import annotations

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Creature, ImageStatus, RecordStatus
from ..schemas import (
    CreateCreatureRequest,
    CreateCreatureResponse,
    CreatureDetail,
    CreatureSummary,
    FavoriteResponse,
    RenameResponse,
)
from ..services import ai, generation, images, library
from .common import XP_CREATE, award_xp, detail, get_creature, get_profile, summary

log = logging.getLogger("chimera.creatures")

router = APIRouter(prefix="/api/creatures", tags=["creatures"])


#: Absolute ceiling for the record phase (~26s typical) — see _generate_task.
RECORD_DEADLINE_S = 180


def spawn(coro, label: str) -> asyncio.Task:
    """create_task + loud death: a background task that raises must never
    vanish silently (asyncio only whispers at GC time)."""
    task = asyncio.create_task(coro)

    def _done(t: asyncio.Task) -> None:
        if not t.cancelled() and t.exception() is not None:
            log.error("background task %s crashed", label, exc_info=t.exception())

    task.add_done_callback(_done)
    return task

CodexSort = Literal["newest", "biggest", "fastest", "strongest", "winners", "favorites"]

#: Codex sorts read as questions, not spreadsheet columns (spec §14).
_STAT_SORTS = {"biggest": "size", "fastest": "speed", "strongest": "power"}


@router.post("", response_model=CreateCreatureResponse)
async def create_creature(
    body: CreateCreatureRequest, db: AsyncSession = Depends(get_db)
) -> CreateCreatureResponse:
    """Fuse four sources into a new chimera.

    The record lands synchronously (stub today, ~16s gpt-5.1 later) and the row
    is saved with image_status=pending. The hero render is a separate, slower
    stage — the frontend polls GET /api/creatures/{id} for the reveal.
    """
    unknown = library.validate_slugs(body.source_slugs)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown source creatures: {unknown}")
    if len(set(body.source_slugs)) != 4:
        raise HTTPException(status_code=400, detail="Pick four different source creatures")

    if not ai.ai_enabled():
        # Stub mode (tests / keyless dev): synchronous record, no image stage.
        record = await generation.generate_creature(body.source_slugs)
        creature = Creature(
            sources=list(body.source_slugs),
            record_status=RecordStatus.complete,
            image_status=ImageStatus.complete,
            records={},
            **_record_fields(record),
        )
        db.add(creature)
        await db.flush()
        award_xp(await get_profile(db), XP_CREATE)
        return CreateCreatureResponse(creature_id=creature.id, status="complete")

    # Real path (Fusion Wait): the button answers instantly with a placeholder
    # row; the record STREAMS in the background, partial fields surface through
    # GET /api/creatures/{id}, and the hero render starts the moment
    # visual_spec finishes streaming.
    creature = Creature(
        name="", rarity="", sources=list(body.source_slugs),
        record_status=RecordStatus.generating,
        image_status=ImageStatus.pending,
        records={},
    )
    db.add(creature)
    await db.flush()
    award_xp(await get_profile(db), XP_CREATE)
    spawn(_generate_task(creature.id, list(body.source_slugs)), f"generate:{creature.id}")
    return CreateCreatureResponse(creature_id=creature.id, status="generating")


def _record_fields(record) -> dict:
    return {
        "name": record.name, "title": record.title, "rarity": record.rarity,
        "role": record.role, "core_stats": record.core_stats.model_dump(),
        "abilities": [a.model_dump() for a in record.abilities],
        "strengths": record.strengths, "weaknesses": record.weaknesses,
        "environment_affinities": record.environment_affinities.model_dump(),
        "sim_profile": record.sim_profile.model_dump(),
        "visual_spec": record.visual_spec, "anatomy_plan": record.anatomy_plan,
        "fun_fact": record.fun_fact,
    }


async def _generate_task(creature_id: int, sources: list[str]) -> None:
    """Owns the whole staged lifecycle for one creature: stream the record
    (hero render fires early on visual_spec), then persist record fields,
    then persist image fields. One writer, its own session — the request
    session is long closed, and no stage may lose an earlier stage's work."""
    from types import SimpleNamespace

    from ..db import session_factory

    hero_task: asyncio.Task | None = None

    async def start_hero(spec: str) -> None:
        nonlocal hero_task
        # Honest BODY FORGE signal: flagged the moment the render task exists,
        # surfaced by detail() until image_status settles.
        generation.PROGRESS.setdefault(creature_id, {})["image_started"] = True
        hero_task = asyncio.create_task(
            images.generate_hero(SimpleNamespace(id=creature_id, visual_spec=spec, name=""))
        )

    log.info("generation task start: creature %s from %s", creature_id, sources)
    async with session_factory()() as db:
        creature = await db.get(Creature, creature_id)
        if creature is None:
            return
        log.info("generation task: row %s loaded, opening record stream", creature_id)
        try:
            # Hard ceiling over the WHOLE record phase. asyncio.wait (not
            # wait_for) so a pathologically uncancellable hang can't take this
            # task down with it: on deadline we abandon the stuck coroutine and
            # land the row in failed/retryable — a creature may never strand at
            # "generating" (observed once: silent hang before the first chunk,
            # inner watchdogs never fired).
            rec_task = asyncio.create_task(
                generation.generate_creature_streaming(
                    creature_id, sources, on_visual_spec=start_hero
                )
            )
            done, _ = await asyncio.wait({rec_task}, timeout=RECORD_DEADLINE_S)
            if rec_task not in done:
                rec_task.cancel()
                raise RuntimeError(
                    f"record generation exceeded {RECORD_DEADLINE_S}s deadline"
                )
            record = rec_task.result()
            for field, value in _record_fields(record).items():
                setattr(creature, field, value)
            creature.record_status = RecordStatus.complete
        except Exception as exc:  # noqa: BLE001 - record failure must land as a state
            log.warning("generation stream failed for %s: %s", creature_id, str(exc)[:200])
            creature.record_status = RecordStatus.failed
            creature.image_status = ImageStatus.failed
            await db.commit()
            generation.PROGRESS.pop(creature_id, None)
            return
        await db.commit()
        # Record fields are persisted; keep only the render-in-flight signal.
        # The whole entry is cleaned up after the image stage commits.
        generation.PROGRESS[creature_id] = {
            "image_started": bool(generation.PROGRESS.get(creature_id, {}).get("image_started"))
        }

        try:
            if hero_task is None:  # visual_spec never fired mid-stream; render now
                generation.PROGRESS[creature_id]["image_started"] = True
                hero = await images.generate_hero(creature)
            else:
                hero = await hero_task
            if hero:
                creature.hero_image_path = hero
                creature.thumb_path = await images.generate_thumb(creature)
                creature.image_status = ImageStatus.complete
            else:
                creature.image_status = ImageStatus.failed
            await db.commit()
        finally:
            generation.PROGRESS.pop(creature_id, None)


@router.post("/{creature_id}/retry-image", response_model=CreateCreatureResponse)
async def retry_image(creature_id: int, db: AsyncSession = Depends(get_db)) -> CreateCreatureResponse:
    """The friendly 'lab is recharging' retry button."""
    creature = await db.get(Creature, creature_id)
    if creature is None:
        raise HTTPException(status_code=404, detail="No such creature")
    if creature.image_status == ImageStatus.pending:
        return CreateCreatureResponse(creature_id=creature.id, status="pending")
    if not ai.ai_enabled():
        raise HTTPException(status_code=409, detail="Image generation is offline")
    creature.image_status = ImageStatus.pending
    await db.flush()
    spawn(_retry_hero_task(creature.id), f"retry-hero:{creature.id}")
    return CreateCreatureResponse(creature_id=creature.id, status="pending")


async def _retry_hero_task(creature_id: int) -> None:
    """Hero-only re-render for the retry button; record is already saved."""
    from ..db import session_factory

    async with session_factory()() as db:
        creature = await db.get(Creature, creature_id)
        if creature is None:
            return
        generation.PROGRESS[creature_id] = {"image_started": True}
        try:
            hero = await images.generate_hero(creature)
            if hero:
                creature.hero_image_path = hero
                creature.thumb_path = await images.generate_thumb(creature)
                creature.image_status = ImageStatus.complete
            else:
                creature.image_status = ImageStatus.failed
            await db.commit()
        finally:
            generation.PROGRESS.pop(creature_id, None)


@router.get("", response_model=list[CreatureSummary])
async def list_creatures(
    sort: CodexSort = Query("newest"), db: AsyncSession = Depends(get_db)
) -> list[CreatureSummary]:
    rows = list((await db.execute(select(Creature))).scalars())

    if sort == "favorites":
        rows = [c for c in rows if c.favorite]
        rows.sort(key=lambda c: c.id, reverse=True)
    elif sort == "winners":
        rows.sort(key=lambda c: (c.championships, c.wins, c.id), reverse=True)
    elif sort in _STAT_SORTS:
        # core_stats is JSON, so ranking happens in Python. Fine at this scale
        # (one player, hundreds of rows) and portable across SQLite/Postgres.
        stat = _STAT_SORTS[sort]
        rows.sort(key=lambda c: ((c.core_stats or {}).get(stat, 0), c.id), reverse=True)
    else:
        rows.sort(key=lambda c: c.id, reverse=True)

    return [summary(c) for c in rows]


@router.get("/{creature_id}", response_model=CreatureDetail)
async def read_creature(creature_id: int, db: AsyncSession = Depends(get_db)) -> CreatureDetail:
    """Full record. `image_status` drives the reveal-screen polling loop."""
    return detail(await get_creature(db, creature_id))


@router.post("/{creature_id}/favorite", response_model=FavoriteResponse)
async def toggle_favorite(
    creature_id: int, db: AsyncSession = Depends(get_db)
) -> FavoriteResponse:
    creature = await get_creature(db, creature_id)
    creature.favorite = not creature.favorite
    return FavoriteResponse(creature_id=creature.id, favorite=creature.favorite)


@router.post("/{creature_id}/rename", response_model=RenameResponse)
async def reroll_name(creature_id: int, db: AsyncSession = Depends(get_db)) -> RenameResponse:
    """Name reroll (spec §11) — a fresh name for the same creature. STUB."""
    creature = await get_creature(db, creature_id)
    name, title = await generation.reroll_name(creature.sources or [], creature.name)
    creature.name, creature.title = name, title
    return RenameResponse(creature_id=creature.id, name=name, title=title)
