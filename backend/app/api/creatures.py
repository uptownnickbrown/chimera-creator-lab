"""Creature creation and the Codex (spec §7 MAKE/REVEAL/COLLECT, §14)."""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Creature, ImageStatus
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

router = APIRouter(prefix="/api/creatures", tags=["creatures"])

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

    record = await generation.generate_creature(body.source_slugs)

    creature = Creature(
        name=record.name,
        title=record.title,
        sources=list(body.source_slugs),
        rarity=record.rarity,
        role=record.role,
        core_stats=record.core_stats.model_dump(),
        abilities=[a.model_dump() for a in record.abilities],
        strengths=record.strengths,
        weaknesses=record.weaknesses,
        environment_affinities=record.environment_affinities.model_dump(),
        sim_profile=record.sim_profile.model_dump(),
        visual_spec=record.visual_spec,
        anatomy_plan=record.anatomy_plan,
        fun_fact=record.fun_fact,
        # AI-enabled: pending until the background render task flips it.
        # Stub mode has no image pipeline, so complete immediately or the
        # reveal screen would poll forever.
        image_status=ImageStatus.pending if ai.ai_enabled() else ImageStatus.complete,
        records={},
    )
    db.add(creature)
    await db.flush()

    award_xp(await get_profile(db), XP_CREATE)
    if creature.image_status == ImageStatus.pending:
        asyncio.create_task(_render_hero_task(creature.id))
    return CreateCreatureResponse(creature_id=creature.id, status=creature.image_status.value)


async def _render_hero_task(creature_id: int) -> None:
    """Background hero render. Owns its own session: the request session is
    closed by the time this runs, and a crash here must never touch the
    already-committed text record."""
    from ..db import session_factory

    async with session_factory()() as db:
        creature = await db.get(Creature, creature_id)
        if creature is None:
            return
        hero = await images.generate_hero(creature)
        if hero:
            creature.hero_image_path = hero
            creature.thumb_path = await images.generate_thumb(creature)
            creature.image_status = ImageStatus.complete
        else:
            creature.image_status = ImageStatus.failed
        await db.commit()


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
    asyncio.create_task(_render_hero_task(creature.id))
    return CreateCreatureResponse(creature_id=creature.id, status="pending")


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
