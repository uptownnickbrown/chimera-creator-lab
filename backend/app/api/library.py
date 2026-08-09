"""Source-creature picker + arena list (spec §22) + Summon New Creature."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas import LibraryResponse, SummonRequest, SummonResponse
from ..services import library as lib
from ..services import summon as summon_svc

router = APIRouter(prefix="/api", tags=["library"])


@router.get("/library", response_model=LibraryResponse)
async def read_library() -> LibraryResponse:
    """Everything the Fusion Lab needs to render its picker.

    Returns an empty `sources` list (and `loaded: false`) until the data files
    are authored — the frontend shows its own empty state rather than erroring.
    `sources` merges the curated parts with every part Henry has summoned.
    """
    return LibraryResponse(sources=lib.sources(), environments=lib.environments(),
                           loaded=lib.is_loaded())


@router.post("/library/summon", response_model=SummonResponse)
async def summon_creature(
    body: SummonRequest, db: AsyncSession = Depends(get_db)
) -> SummonResponse:
    """Type ANY animal — real, extinct, mythical, or misspelled.

    matched      -> an existing part (local alias hit or resolver misspelling)
    disambiguate -> 2-3 candidates for the "Did you mean?" cards
    conjured     -> a brand-new custom part; portrait renders in the background
    redirect     -> a kind, playful, kid-safe line steering back to animals
    """
    return await summon_svc.summon(db, body.query)
