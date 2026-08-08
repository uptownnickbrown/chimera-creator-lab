"""Player profile and the Hall of Champions (spec §16)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Creature
from ..schemas import HallRecord, HallView, ProfileView
from .common import XP_PER_LEVEL, get_profile, summary

router = APIRouter(prefix="/api", tags=["profile"])


def _top(rows: list[Creature], stat: str) -> Creature | None:
    return max(rows, key=lambda c: (c.core_stats or {}).get(stat, 0), default=None)


@router.get("/profile", response_model=ProfileView)
async def read_profile(db: AsyncSession = Depends(get_db)) -> ProfileView:
    profile = await get_profile(db)
    rows = list((await db.execute(select(Creature))).scalars())

    champion = max(
        (c for c in rows if c.championships > 0),
        key=lambda c: (c.championships, c.wins),
        default=None,
    )
    biggest = _top(rows, "size")

    return ProfileView(
        name=profile.name,
        avatar=profile.avatar,
        level=profile.level,
        xp=profile.xp,
        xp_to_next=XP_PER_LEVEL - (profile.xp % XP_PER_LEVEL),
        settings=profile.settings or {},
        total_creatures=len(rows),
        battles_won=sum(c.wins for c in rows),
        biggest_creature=summary(biggest) if biggest else None,
        current_champion=summary(champion) if champion else None,
        favorites=[summary(c) for c in sorted(
            (c for c in rows if c.favorite), key=lambda c: c.id, reverse=True)][:4],
    )


@router.get("/hall", response_model=HallView)
async def read_hall(db: AsyncSession = Depends(get_db)) -> HallView:
    """Champions, top winners, and the fun records that make old creatures matter."""
    rows = list((await db.execute(select(Creature))).scalars())

    champions = sorted(
        (c for c in rows if c.championships > 0),
        key=lambda c: (c.championships, c.wins),
        reverse=True,
    )
    top_winners = sorted(rows, key=lambda c: (c.wins, c.championships), reverse=True)[:5]
    top_winners = [c for c in top_winners if c.wins > 0]

    records: list[HallRecord] = []
    for key, label, stat in (
        ("biggest", "Biggest Creature", "size"),
        ("fastest", "Fastest Creature", "speed"),
        ("strongest", "Strongest Bite", "power"),
    ):
        best = _top(rows, stat)
        if best is not None:
            records.append(HallRecord(
                key=key, label=label,
                value=str((best.core_stats or {}).get(stat, 0)),
                creature=summary(best),
            ))

    most_wins = top_winners[0] if top_winners else None
    if most_wins is not None:
        records.append(HallRecord(
            key="most_wins", label="Most Wins",
            value=str(most_wins.wins), creature=summary(most_wins),
        ))

    return HallView(
        champions=[summary(c) for c in champions],
        top_winners=[summary(c) for c in top_winners],
        records=records,
    )
