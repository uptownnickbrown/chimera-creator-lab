"""Source-creature picker + arena list (spec §22) + Summon New Creature."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..models import CustomPart
from ..schemas import DeleteCustomPartResponse, LibraryResponse, SummonRequest, SummonResponse
from ..services import library as lib
from ..services import summon as summon_svc

log = logging.getLogger("chimera.library.api")

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


@router.delete("/library/custom/{slug:path}", response_model=DeleteCustomPartResponse)
async def delete_custom_part(
    slug: str, db: AsyncSession = Depends(get_db)
) -> DeleteCustomPartResponse:
    """Delete one SUMMONED part (row + live registry entry + portrait file).

    Accepts the bare slug or the full `custom/<slug>` form. The 160 curated
    parts are never deletable — asking returns 403. Creatures already fused
    from the deleted part keep working: their `sources` list keeps the slug
    and display degrades to a title-cased ghost name.
    """
    bare = slug.removeprefix("custom/")
    full = f"custom/{bare}"

    row = (await db.execute(
        select(CustomPart).where(CustomPart.slug == full)
    )).scalar_one_or_none()
    if row is None:
        curated = lib.source_by_slug(bare)
        if curated is not None and not curated.custom:
            raise HTTPException(
                status_code=403, detail=f"{curated.name} is a curated part and cannot be deleted"
            )
        raise HTTPException(status_code=404, detail=f"No summoned part {full}")

    await db.delete(row)
    lib.remove_custom(full)

    # Portrait files are keyed on the slash-flattened slug (services/summon.py).
    portrait = get_settings().media_dir / "parts" / f"{full.replace('/', '_')}.png"
    try:
        portrait.unlink(missing_ok=True)
    except OSError as exc:  # best-effort: media cleanup never fails a delete
        log.warning("delete: could not remove portrait %s: %s", portrait.name, exc)
    return DeleteCustomPartResponse(slug=full)
