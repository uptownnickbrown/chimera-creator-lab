#!/usr/bin/env python
"""Starter-crew seed pipeline: 8 pregenerated chimeras committed to the repo.

Runs the REAL production pipeline (services/generation.py + services/images.py)
so seed creatures are indistinguishable from runtime ones:
  record  — gpt-5.1 structured output via generate_creature(), with a target-
            rarity hint appended so the crew is a believable rarity mix
  hero    — gpt-image-1.5 quality=high at HERO_SIZE via the shared
            images.hero_prompt() builder, transparent background (verified
            programmatically: all four corner pixels must have alpha == 0)
  thumb   — images._thumb_from_hero_bytes() alpha-bbox head crop

Output (committed after art review):
  data/seed/<key>/record.json   full CreatureRecord dump + sources list
  data/seed/<key>/hero.webp
  data/seed/<key>/thumb.webp
  data/seed/manifest.json       keys in bracket-seed order

Resumable: a recipe whose three files already exist is skipped; a recipe with
only record.json resumes at the hero render. `--only <key>` runs one recipe.

Usage:  .venv/bin/python scripts/gen_seed_creatures.py [--only <key>]
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas import CreatureRecord
from app.services import ai, generation, images
from app.services import library as library_svc

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("seed-pipeline")

SEED_DIR = ROOT / "data" / "seed"

#: (key, four source slugs, target rarity) in bracket-seed order. Fixed recipe.
RECIPES: list[tuple[str, list[str], str]] = [
    ("sky_hunter", ["thunderbird", "quetzalcoatlus", "peregrine-falcon", "harpy-eagle"], "Epic"),
    ("deep_titan", ["leviathan", "megalodon", "electric-eel", "anglerfish"], "Legendary"),
    ("ember_tank", ["flame-salamander", "ankylosaurus", "pangolin", "gila-monster"], "Rare"),
    ("frost_pack", ["fenrir", "dire-wolf", "snow-leopard", "wolverine"], "Epic"),
    ("shadow_trick", ["kitsune", "microraptor", "chameleon", "octopus"], "Rare"),
    ("swamp_king", ["hydra", "sarcosuchus", "king-cobra", "alligator-snapping-turtle"], "Rare"),
    ("dune_guard", ["stone-golem", "glyptodon", "scorpion", "thorny-devil"], "Uncommon"),
    ("ever_pal", ["phoenix", "dodo", "axolotl", "immortal-jellyfish"], "Uncommon"),
]

#: Extra flavor appended per-recipe (only where the crew concept needs it).
THEME_NOTES = {
    "ever_pal": (
        "Theme: adorable and impossible to defeat permanently — it always comes "
        "back, a regeneration comedy. Kids should want to hug it."
    ),
}

RARITY_ORDER = ["Uncommon", "Rare", "Epic", "Legendary"]


def rarity_drift(actual: str, target: str) -> int:
    return abs(RARITY_ORDER.index(actual) - RARITY_ORDER.index(target))


def corners_transparent(png_bytes: bytes) -> bool:
    """Real alpha check: all four corner pixels must be fully transparent."""
    from PIL import Image

    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    w, h = img.size
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    return all(img.getpixel(p)[3] == 0 for p in corners)


async def gen_record(key: str, sources: list[str], target: str) -> CreatureRecord:
    """generate_creature() with the rarity target; regenerate once on 2+ tier drift."""
    extra = (
        f"Target rarity for this creature: {target}. "
        "Make the record coherent with that power level."
    )
    if key in THEME_NOTES:
        extra += f"\n{THEME_NOTES[key]}"

    record = await generation.generate_creature(sources, extra_instructions=extra)
    d = rarity_drift(record.rarity, target)
    log.info("[%s] record: %r (%s) — target %s, drift %d", key, record.name, record.rarity,
             target, d)
    if d >= 2:
        log.warning("[%s] rarity %s is %d tiers off target %s — regenerating once",
                    key, record.rarity, d, target)
        second = await generation.generate_creature(sources, extra_instructions=extra)
        d2 = rarity_drift(second.rarity, target)
        log.info("[%s] regen record: %r (%s) — drift %d", key, second.name, second.rarity, d2)
        if d2 < d:
            record = second
    return record


async def render_hero(key: str, record: CreatureRecord) -> bytes:
    """Real hero render: shared prompt builder, quality=high, HERO_SIZE, verified alpha."""
    prompt = images.hero_prompt(record)
    for attempt in range(1, 4):
        t0 = time.monotonic()
        png = await images._render(prompt, quality="high", size=images.HERO_SIZE)
        took = time.monotonic() - t0
        if corners_transparent(png):
            log.info("[%s] hero: %dKB in %.0fs (attempt %d, alpha verified)",
                     key, len(png) // 1024, took, attempt)
            return png
        log.warning("[%s] hero attempt %d has opaque corners — re-rendering", key, attempt)
    raise RuntimeError(f"[{key}] no transparent hero after 3 attempts")


async def build_recipe(key: str, sources: list[str], target: str) -> None:
    out = SEED_DIR / key
    out.mkdir(parents=True, exist_ok=True)
    record_path = out / "record.json"
    hero_path = out / f"hero{images.MEDIA_EXT}"
    thumb_path = out / f"thumb{images.MEDIA_EXT}"

    if record_path.exists() and hero_path.exists() and thumb_path.exists():
        log.info("[%s] complete — skipping", key)
        return

    if record_path.exists():
        record = CreatureRecord.model_validate(json.loads(record_path.read_text())["record"])
        log.info("[%s] resuming with existing record %r (%s)", key, record.name, record.rarity)
    else:
        record = await gen_record(key, sources, target)
        record_path.write_text(json.dumps(
            {"key": key, "sources": sources, "target_rarity": target,
             "record": record.model_dump()},
            indent=2,
        ) + "\n")
        log.info("[%s] wrote %s", key, record_path)

    if hero_path.exists():
        hero_png = None
        log.info("[%s] hero art already present — skipping render", key)
    else:
        hero_png = await render_hero(key, record)
        hero_path.write_bytes(images.to_webp(hero_png))
        log.info("[%s] wrote %s", key, hero_path)

    if not thumb_path.exists():
        # _thumb_from_hero_bytes reads whatever Pillow can open and always
        # writes WebP, so a resumed run can derive the thumb from the file.
        source = hero_png if hero_png is not None else hero_path.read_bytes()
        thumb_path.write_bytes(images._thumb_from_hero_bytes(source))
        log.info("[%s] wrote %s", key, thumb_path)


def complete_keys() -> list[str]:
    done = []
    for key, _, _ in RECIPES:
        d = SEED_DIR / key
        if all((d / f).exists() for f in
               ("record.json", f"hero{images.MEDIA_EXT}", f"thumb{images.MEDIA_EXT}")):
            done.append(key)
    return done


def write_manifest() -> None:
    keys = complete_keys()
    (SEED_DIR / "manifest.json").write_text(
        json.dumps({"keys": keys}, indent=2) + "\n"
    )
    log.info("manifest: %d/%d complete — %s", len(keys), len(RECIPES), keys)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", metavar="KEY", help="run a single recipe key")
    args = parser.parse_args()

    if not ai.ai_enabled():
        log.error("OPEN_AI_API_KEY not available (or CHIMERA_STUB_AI=1) — seeds must be "
                  "generated by the REAL pipeline; aborting.")
        return 1

    library_svc.load_library()
    recipes = [r for r in RECIPES if not args.only or r[0] == args.only]
    if not recipes:
        log.error("--only %r matches no recipe key", args.only)
        return 1

    failures = []
    for key, sources, target in recipes:
        try:
            await build_recipe(key, sources, target)
        except Exception as exc:  # noqa: BLE001 - keep going; report at the end
            log.error("[%s] FAILED: %s", key, str(exc)[:300])
            failures.append(key)

    write_manifest()
    if failures:
        log.error("failed recipes (re-run to resume): %s", failures)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
