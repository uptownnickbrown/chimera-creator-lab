"""Hero-image pipeline (docs/AI_CONTRACTS.md §1B, §3).

gpt-image-1.5 with `background=transparent` — the only bakeoff model with
native alpha, which matters for translucent flame/lightning/spray edges that
a chroma key destroys. OpenAI-only by decision; on repeated failure we mark
the row `failed` and the UI offers a friendly retry ("the lab is recharging").

Files land in the backend-owned media dir (served at /media by the API, so
prod does not depend on writing into the frontend image). A creature row is
created with image_status=pending; the text record is already saved, so
nothing here may ever lose a creature.
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging

from ..config import get_settings
from ..models import Creature

log = logging.getLogger("chimera.images")

HERO_SIZE = "1536x1024"
KEYART_SIZE = "1536x1024"
THUMB_PX = 512

HERO_STYLE = (
    "Epic realistic fantasy creature concept art for a AAA video game. "
    "Cinematic dramatic lighting, hyper-detailed textures, museum-quality "
    "creature design. The creature is ONE coherent invented species. Full "
    "body visible, dynamic three-quarter hero pose, not touching the image "
    "edges. Fierce and epic but suitable for a 7-year-old: no gore, no "
    "blood. Absolutely no text, letters, numbers, logos, or watermarks. "
    "Transparent background — the isolated creature ONLY: no scenery, no "
    "terrain base, no backdrop or environment, even if the description "
    "mentions surroundings (at most a soft contact shadow under its feet). "
    "Creature description: "
)


def _media_dir():
    d = get_settings().media_dir / "creatures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def hero_prompt(record_like) -> str:
    """The one true hero prompt. Used by the runtime render path AND the seed
    pipeline (scripts/gen_seed_creatures.py) so pregenerated art is guaranteed
    to match runtime art. `record_like` needs `.visual_spec` and `.name`."""
    return HERO_STYLE + (record_like.visual_spec or record_like.name)


async def _render(prompt: str, *, quality: str, size: str = HERO_SIZE) -> bytes:
    from . import ai

    resp = await ai.client().images.generate(
        model=ai.IMAGE_MODEL, prompt=prompt, size=size, quality=quality,
        background="transparent", output_format="png",
    )
    return base64.b64decode(resp.data[0].b64_json)


async def generate_hero(creature: Creature) -> str | None:
    """Render the transparent hero PNG; return its web path or None.

    Attempts: high → high (retry) → medium (verified fast path). None only
    after all three fail; caller sets image_status=failed.
    """
    from . import ai

    if not ai.ai_enabled():
        log.info("images: AI disabled — no hero for creature %s", creature.id)
        return None

    prompt = hero_prompt(creature)
    for attempt, quality in enumerate(("high", "high", "medium"), 1):
        try:
            png = await _render(prompt, quality=quality)
            path = _media_dir() / f"{creature.id}.png"
            path.write_bytes(png)
            log.info("images: hero for %s (%s, attempt %d, %dKB)",
                     creature.id, quality, attempt, len(png) // 1024)
            return f"/media/creatures/{creature.id}.png"
        except Exception as exc:  # noqa: BLE001 - API errors: log and retry
            log.warning("images: hero attempt %d (%s) failed for %s: %s",
                        attempt, quality, creature.id, str(exc)[:200])
            await asyncio.sleep(2 * attempt)
    return None


def _thumb_from_hero_bytes(hero_png: bytes) -> bytes:
    """Alpha-aware square crop biased toward the creature's head (top third)."""
    from PIL import Image

    img = Image.open(io.BytesIO(hero_png)).convert("RGBA")
    bbox = img.getchannel("A").point(lambda a: 255 if a > 20 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    side = min(img.width, img.height)
    left = (img.width - side) // 2
    img = img.crop((left, 0, left + side, side))
    img = img.resize((THUMB_PX, THUMB_PX), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


async def generate_thumb(creature: Creature) -> str | None:
    """Derive the codex thumbnail from the saved hero PNG. Local, instant."""
    hero = _media_dir() / f"{creature.id}.png"
    if not hero.exists():
        return None
    thumb = _media_dir() / f"{creature.id}_thumb.png"
    thumb.write_bytes(await asyncio.to_thread(_thumb_from_hero_bytes, hero.read_bytes()))
    return f"/media/creatures/{creature.id}_thumb.png"


async def generate_championship_art(fa: Creature, fb: Creature) -> str | None:
    """Finals key art via images.edit with both hero cutouts (bakeoff-validated
    for two-creature identity preservation).

    Generated when the FINALISTS are known (semifinals complete), before the
    winner is — so the scene is a neutral titanic clash, and the ~74s render
    hides inside the final prediction + battle. Championship only, never
    blocking: None simply means the ceremony uses the composited finale.
    """
    from . import ai

    if not ai.ai_enabled():
        return None
    a = _media_dir() / f"{fa.id}.png"
    b = _media_dir() / f"{fb.id}.png"
    if not (a.exists() and b.exists()):
        return None

    prompt = (
        "Epic cinematic championship key art for a AAA monster game, child-"
        "friendly (no gore, no blood). The FIRST attached creature and the "
        "SECOND attached creature clash mid-battle in a futuristic holographic "
        "grand arena at night — gold championship light beams, violet and "
        "cyan energy, sparks and spray flying, both titans rearing at each "
        "other in a perfectly balanced duel, neither winning. Keep BOTH "
        "creatures' designs EXACTLY as shown in the attached images — same "
        "anatomy, colors, plates, proportions. No text or watermarks."
    )
    try:
        resp = await ai.client().images.edit(
            model=ai.IMAGE_MODEL,
            image=[(f"{fa.id}.png", io.BytesIO(a.read_bytes()), "image/png"),
                   (f"{fb.id}.png", io.BytesIO(b.read_bytes()), "image/png")],
            prompt=prompt, size=KEYART_SIZE, quality="high", output_format="png",
        )
        png = base64.b64decode(resp.data[0].b64_json)
        lo, hi = sorted((fa.id, fb.id))
        path = _media_dir() / f"final_{lo}_{hi}.png"
        path.write_bytes(png)
        return f"/media/creatures/final_{lo}_{hi}.png"
    except Exception as exc:  # noqa: BLE001 - ceremony must never block
        log.warning("images: championship art failed (%s vs %s): %s",
                    fa.id, fb.id, str(exc)[:200])
        return None
