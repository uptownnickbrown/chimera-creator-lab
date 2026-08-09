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


# Summoned-part portraits must sit in the same visual family as the 160
# pregenerated picker portraits. Style + isolation language is copied VERBATIM
# from the pregen pipeline (scripts/assetlib.py PORTRAIT_STYLE and
# scripts/generate_assets.py PORTRAIT_ISOLATION) — keep the three in sync.
PART_PORTRAIT_STYLE = (
    "Realistic AAA creature portrait for a neon sci-fi game, aimed at kids "
    "7-10. The creature keeps its NATURAL realistic coloring and detailed "
    "texture, lit dramatically with a subtle electric-cyan and violet rim "
    "light as if standing in a dark holographic lab. Epic, fierce, premium — "
    "never gory. Full body visible, three-quarter dramatic pose, centered, "
    "not touching image edges. Absolutely no text or watermarks. "
)
PART_PORTRAIT_ISOLATION = (
    " CRITICAL: this is a cut-out sprite of the creature ALONE. Do not paint "
    "any scenery, environment, habitat, ground, floor, terrain, rock, water, "
    "waves, snow, lava, sand, clouds, sky, mist, smoke, dust, moon, or cast "
    "shadow. No base, no platform, no pedestal, no rectangular backdrop panel, "
    "no vignette. Everything that is not the creature's own body must be "
    "completely empty and fully transparent, right up to its silhouette. "
    "Effects like fire or lightning are allowed only where they touch the "
    "creature's own body. Transparent background."
)
PART_SIZE = "1024x1024"


def _media_dir():
    d = get_settings().media_dir / "creatures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parts_dir():
    d = get_settings().media_dir / "parts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def part_portrait_prompt(name: str, description: str) -> str:
    """Exactly the pregen part-portrait prompt shape (generate_assets.py)."""
    return (PART_PORTRAIT_STYLE + "Creature: " + name + ". " +
            description.rstrip(".") + "." + PART_PORTRAIT_ISOLATION)


async def generate_part_portrait(file_slug: str, name: str, description: str) -> str | None:
    """Render a summoned part's picker portrait; return its web path or None.

    quality=medium (~26s, the verified fast path) — a picker card, not a hero
    render. Two attempts, then None; the caller marks the row failed.
    """
    from . import ai

    if not ai.ai_enabled():
        log.info("images: AI disabled — no portrait for part %s", file_slug)
        return None

    prompt = part_portrait_prompt(name, description)
    for attempt in (1, 2):
        try:
            png = await _render(prompt, quality="medium", size=PART_SIZE)
            path = _parts_dir() / f"{file_slug}.png"
            path.write_bytes(png)
            log.info("images: part portrait %s (attempt %d, %dKB)",
                     file_slug, attempt, len(png) // 1024)
            return f"/media/parts/{file_slug}.png"
        except Exception as exc:  # noqa: BLE001 - API errors: log and retry
            log.warning("images: part portrait attempt %d failed for %s: %s",
                        attempt, file_slug, str(exc)[:200])
            await asyncio.sleep(2 * attempt)
    return None


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
    """Alpha-aware square FIT: the whole creature, never a crop.

    A square crop chopped wide creatures (wings, serpent coils) at the card
    edge. Instead: tight alpha bbox, then letterbox onto a transparent square
    with a small margin so every silhouette reads complete in the Codex.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(hero_png)).convert("RGBA")
    bbox = img.getchannel("A").point(lambda a: 255 if a > 20 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    side = max(img.width, img.height)
    margin = max(2, side // 25)
    canvas = Image.new("RGBA", (side + 2 * margin,) * 2, (0, 0, 0, 0))
    canvas.paste(img, ((canvas.width - img.width) // 2, (canvas.height - img.height) // 2))
    canvas = canvas.resize((THUMB_PX, THUMB_PX), Image.LANCZOS)
    out = io.BytesIO()
    canvas.save(out, "PNG")
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
