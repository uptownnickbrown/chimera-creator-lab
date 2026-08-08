"""Source-creature picker + arena list (spec §22)."""
from __future__ import annotations

from fastapi import APIRouter

from ..schemas import LibraryResponse
from ..services import library as lib

router = APIRouter(prefix="/api", tags=["library"])


@router.get("/library", response_model=LibraryResponse)
async def read_library() -> LibraryResponse:
    """Everything the Fusion Lab needs to render its picker.

    Returns an empty `sources` list (and `loaded: false`) until the data files
    are authored — the frontend shows its own empty state rather than erroring.
    """
    return LibraryResponse(sources=lib.sources(), environments=lib.environments(),
                           loaded=lib.is_loaded())
