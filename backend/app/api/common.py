"""Shared router helpers: row -> response-model conversion, profile access."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Creature, Profile, RecordStatus
from ..schemas import CreatureDetail, CreatureSummary
from ..services import generation

XP_PER_LEVEL = 200
XP_CREATE = 10
XP_CORRECT_PREDICTION = 25


def summary(c: Creature) -> CreatureSummary:
    return CreatureSummary(
        id=c.id,
        name=c.name,
        title=c.title,
        rarity=c.rarity,
        role=c.role,
        sources=c.sources or [],
        core_stats=c.core_stats or {},
        record_status=(
            c.record_status.value if hasattr(c.record_status, "value") else c.record_status
        ),
        image_status=c.image_status.value if hasattr(c.image_status, "value") else c.image_status,
        hero_image_path=c.hero_image_path,
        thumb_path=c.thumb_path,
        favorite=c.favorite,
        wins=c.wins,
        losses=c.losses,
        championships=c.championships,
        created_at=c.created_at,
    )


def detail(c: Creature) -> CreatureDetail:
    fought = c.wins + c.losses
    base = summary(c).model_dump()
    if c.record_status == RecordStatus.generating:
        # Fusion Wait: overlay whatever the record stream has revealed so far
        # (name at ~8s, stats ticking in after) onto the placeholder row.
        partial = generation.PROGRESS.get(c.id, {})
        for key in ("name", "title", "rarity"):
            if partial.get(key):
                base[key] = partial[key]
        if partial.get("core_stats"):
            base["core_stats"] = partial["core_stats"]
        if partial.get("ability_names"):
            base["ability_names"] = partial["ability_names"]
    return CreatureDetail(
        **base,
        abilities=c.abilities or [],
        strengths=c.strengths or [],
        weaknesses=c.weaknesses or [],
        environment_affinities=c.environment_affinities or {},
        fun_fact=c.fun_fact,
        anatomy_plan=c.anatomy_plan,
        visual_spec=c.visual_spec,
        records=c.records or {},
        win_rate=round(100 * c.wins / fought) if fought else 0,
    )


async def get_creature(db: AsyncSession, creature_id: int) -> Creature:
    row = await db.get(Creature, creature_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No creature {creature_id}")
    return row


async def get_profile(db: AsyncSession) -> Profile:
    """The one and only profile row, created on first access."""
    row = (await db.execute(select(Profile).limit(1))).scalar_one_or_none()
    if row is None:
        row = Profile(id=1, name=get_settings().player_name, settings={})
        db.add(row)
        await db.flush()
    return row


def award_xp(profile: Profile, amount: int) -> None:
    profile.xp += amount
    profile.level = 1 + profile.xp // XP_PER_LEVEL
