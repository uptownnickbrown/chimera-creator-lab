#!/usr/bin/env python3
"""Generate the 5 style-anchor assets for visual review BEFORE the full batch.

These anchors become images.edit references for their families.
"""

import concurrent.futures as cf
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from assetlib import PORTRAIT_STYLE, ROOT, STYLE, finalize, finalize_opaque, generate

ENVS = json.loads((ROOT / "data" / "environments.json").read_text())
PARTS = json.loads((ROOT / "data" / "source_creatures.json").read_text())


def lab_background():
    p = generate(
        STYLE + "Wide interior establishing shot of the creature laboratory "
        "itself: a vast dark sci-fi hall receding into bokeh depth, distant "
        "holographic machinery and glowing conduits, subtle cyan and violet "
        "atmosphere, dark enough that bright UI panels will sit on top of it "
        "legibly. Empty floor center stage. Moody, premium, calm.",
        "lab_background", size="1536x1024", transparent=False)
    finalize_opaque(p, "lab/background", 1920, 1080)


def platform():
    p = generate(
        STYLE + "A large empty holographic creature display platform seen "
        "from slightly above and in front: a wide circular dark glass base "
        "with concentric rings of electric cyan light, a soft column of "
        "rising light particles above it, violet energy filigree around the "
        "rim. Isolated object on transparent background, nothing else.",
        "lab_platform", size="1536x1024")
    finalize(p, "lab/platform", 1536, 640, margin=0.02)


def fusion_chamber():
    p = generate(
        STYLE + "The fusion chamber mid-activation: four curved dark-metal "
        "electrode arms arranged around a swirling violet-purple energy "
        "vortex, streams of light particles converging toward the glowing "
        "core, arcs of cyan electricity between the arms. Isolated object on "
        "transparent background.",
        "lab_fusion_chamber", size="1024x1024")
    finalize(p, "lab/fusion_chamber", 1024, 1024, margin=0.02)


def env_storm_coast():
    e = next(x for x in ENVS if x["slug"] == "storm-coast")
    p = generate(
        STYLE + "Wide establishing shot of an epic monster battle arena, no "
        "creatures present, dramatic depth, open space at center for two "
        "large combatants. Scene: " + e["visual_hint"],
        "env_storm-coast", size="1536x1024", transparent=False)
    finalize_opaque(p, "env/storm-coast", 1536, 1024)
    finalize_opaque(p, "env/storm-coast_card", 640, 360)


def part_dragon():
    c = next(x for x in PARTS if x["slug"] == "dragon")
    p = generate(
        PORTRAIT_STYLE + "Creature: " + c["name"] + ". " + c["visual_hint"] +
        ". Transparent background.",
        "part_dragon", size="1024x1024")
    finalize(p, "parts/dragon", 1024, 1024)


if __name__ == "__main__":
    jobs = [lab_background, platform, fusion_chamber, env_storm_coast, part_dragon]
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(j): j.__name__ for j in jobs}
        for f in cf.as_completed(futs):
            name = futs[f]
            try:
                f.result()
                print("DONE", name)
            except Exception as e:
                print("FAIL", name, str(e)[:200])
