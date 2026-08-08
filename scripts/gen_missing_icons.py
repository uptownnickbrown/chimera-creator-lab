#!/usr/bin/env python3
"""Icons for slots the frontend needs that the original wishlist missed."""
import concurrent.futures as cf
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from assetlib import finalize, generate

ICON_STYLE = (
    "Bold glowing holographic sigil icon for a kids' neon sci-fi game UI. "
    "Single subject, solid filled chunky silhouette readable at 28 pixels, "
    "no thin lines, no wireframe. Brilliant saturated electric cyan with a "
    "white-hot core and soft cyan bloom, like a heavy neon glyph. Flat-ish "
    "emblem, not a scene, no perspective, no background, no frame, no text, "
    "no letters, no numbers. Transparent background. Subject: "
)

ICONS = {
    "icons/nav_home": "a simple house emblem",
    "icons/nav_fusion": "a laboratory flask with an energy vortex swirling inside",
    "icons/nav_codex": "an open book with a creature paw mark on its pages",
    "icons/nav_arena": "two crossed swords",
    "icons/xp": "a faceted hexagonal energy crystal",
    "icons/endurance": "a heart with a pulse line through it",
    "icons/range": "an archery target with an arrow in the bullseye",
    "icons/ability_generic": "a four-pointed energy starburst",
    "icons/fact_fun": "a sparkling four-point star with small orbiting sparkles",
    "icons/tile_create": "a laboratory flask with an energy vortex, slightly larger emblem",
    "icons/tile_codex": "an open holographic book",
    "icons/tile_arena": "two crossed swords over a small shield",
    "icons/tile_hall": "a champion trophy cup",
}


def gen(slot, subject):
    p = generate(ICON_STYLE + subject + ".", slot.replace("/", "_"),
                 size="1024x1024", transparent=True)
    finalize(p, slot, 256, 256)
    return slot


def logo():
    p = generate(
        "Bold emblem mark for a kids' neon sci-fi creature laboratory game: a "
        "stylized creature claw print fused with a DNA double-helix strand, "
        "violet-to-cyan holographic gradient, solid chunky shapes, glowing, "
        "flat emblem, no background, no text, no letters. Transparent background.",
        "ui_logo_mark", size="1024x1024", transparent=True)
    finalize(p, "ui/logo_mark", 512, 512)
    return "ui/logo_mark"


jobs = [lambda s=s, d=d: gen(s, d) for s, d in ICONS.items()] + [logo]
with cf.ThreadPoolExecutor(max_workers=6) as ex:
    for f in cf.as_completed([ex.submit(j) for j in jobs]):
        try:
            print("DONE", f.result())
        except Exception as e:
            print("FAIL", str(e)[:150])
