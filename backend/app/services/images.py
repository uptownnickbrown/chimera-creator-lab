"""Hero-image pipeline — INTERFACE ONLY, nothing implemented yet.

Per ARCHITECTURE.md the runtime hero render is gpt-image-1.5 with
`background=transparent`, quality high, 1536x1024, ~50s. It is the only model
in the bakeoff with native alpha, which matters for translucent flame/lightning
/spray edges that a chroma key destroys.

Contract for whoever implements this:
- Creature rows are created with `image_status = pending`; text is already
  saved, so a failure here must never lose the record. Retry once, then fall
  back to gemini-3.1-flash-image, then mark `failed` and move on.
- Write the PNG under `frontend/public/assets/creatures/<id>.png` (committed art,
  Agora-style) and store the web path on the row.
- Images contain ZERO text — the UI renders all typography.
"""
from __future__ import annotations

import logging

from ..models import Creature

log = logging.getLogger("chimera.images")

HERO_SIZE = "1536x1024"
HERO_MODEL = "gpt-image-1.5"
FALLBACK_MODEL = "gemini-3.1-flash-image"
ASSET_DIR = "frontend/public/assets/creatures"


async def generate_hero(creature: Creature) -> str | None:
    """Render the transparent-background hero PNG; return its web path.

    TODO: call gpt-image-1.5 with `creature.visual_spec`, background=transparent,
    quality=high, size=HERO_SIZE. On success write the file and return
    "/assets/creatures/<id>.png". On failure retry once, then FALLBACK_MODEL,
    then return None so the caller can set image_status=failed.
    """
    log.info("images: generate_hero not implemented yet (creature=%s)", creature.id)
    return None


async def generate_thumb(creature: Creature) -> str | None:
    """Derive the codex thumbnail crop from the hero PNG (Pillow, square crop).

    TODO: alpha-bbox the hero, square-crop around the head, resize to 512px.
    """
    log.info("images: generate_thumb not implemented yet (creature=%s)", creature.id)
    return None


async def generate_championship_art(winner: Creature, loser: Creature) -> str | None:
    """Championship-final key art only (ARCHITECTURE.md: not per-battle).

    TODO: gpt-image-1.5 images.edit with both hero cutouts as reference images,
    which the bakeoff validated for two-creature identity preservation.
    """
    log.info("images: championship art not implemented yet (%s vs %s)", winner.id, loser.id)
    return None
