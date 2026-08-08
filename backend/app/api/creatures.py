"""Creature creation and the Codex (spec §7 MAKE/REVEAL/COLLECT, §14)."""
from __future__ import annotations

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
from ..services import generation, library
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
        # STUB: with no image pipeline wired, the reveal would otherwise poll
        # forever. Real impl sets `pending` here and flips it from the render task.
        image_status=ImageStatus.complete,
        records={},
    )
    db.add(creature)
    await db.flush()

    award_xp(await get_profile(db), XP_CREATE)
    return CreateCreatureResponse(creature_id=creature.id, status=creature.image_status.value)


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
