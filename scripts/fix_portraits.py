#!/usr/bin/env python3
"""Targeted portrait regenerations from Nick's QA notes (2026-08-08).

Root cause for the dragon-lookalikes: the shared dragon style-reference bled
its SUBJECT into some renders. These fixes drop the image reference (style
lives in the prompt) and pin the anatomy explicitly.
"""
import concurrent.futures as cf
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from assetlib import PORTRAIT_STYLE, ROOT, finalize, generate

HINTS = {x["slug"]: x for x in json.loads((ROOT / "data" / "source_creatures.json").read_text())}

FIXES = {
    "stegosaurus": "It has exactly ONE tail, ending in four thagomizer spikes. No second tail.",
    "anglerfish": "Jaws open and PACKED with long translucent needle teeth clearly visible inside the mouth; glowing lure lit; the mouth interior shows teeth and tongue, not an empty void.",
    "spinosaurus": "Long crocodilian jaws lined with visible conical teeth top and bottom; mouth interior detailed, never an empty hollow.",
    "quetzalcoatlus": "Correct pterosaur anatomy: its WINGS ARE ITS FRONT LIMBS - exactly two membrane wings and two hind legs, four limbs total. Standing tall on folded wing-knuckles and hind legs like a giraffe-sized pterosaur, never four legs plus separate wings.",
    "behemoth": "A colossal WINGLESS earth titan: bull-bison silhouette, boulder shoulders, stone-plated hide with moss, blunt curved horns, heavy jaw. Absolutely NO wings, NO reptilian dragon features, NO fire.",
    "couatl": "The ENTIRE creature including both fully spread feathered wings fits comfortably inside the frame with generous empty margin on all sides; nothing crops at any edge.",
    "flame-salamander": "A glossy black AMPHIBIAN salamander with vivid orange flame markings, wide flat head, smooth moist skin, low crawling posture on four short legs, long tapering tail wreathed in small flames. NO wings, NO scales, NOT a dragon.",
    "giant-ground-sloth": "Each forepaw bears exactly THREE huge curved digging claws; shaggy fur, standing upright against a tree.",
    "manta-ray": "A REAL manta ray: flat diamond-shaped body, two broad wing-like pectoral fins, cephalic head fins curled forward, long thin tail, black back and white belly, gliding pose. It is a fish - no legs, no neck, no dragon features.",
    "therizinosaurus": "Each hand bears exactly THREE enormous scythe-like claws (six total); pot-bellied feathered dinosaur body, long neck, small head.",
}


def fix(slug: str) -> str:
    c = HINTS[slug]
    prompt = (PORTRAIT_STYLE + "Creature: " + c["name"] + ". " + c["visual_hint"] +
              ". IMPORTANT anatomical requirements: " + FIXES[slug] +
              " The creature is fully inside the frame, not touching any edge. "
              "Transparent background.")
    p = generate(prompt, f"part_{slug}_fix", size="1024x1024", transparent=True)
    finalize(p, f"parts/{slug}", 1024, 1024, margin=0.06)
    return slug


with cf.ThreadPoolExecutor(max_workers=5) as ex:
    for f in cf.as_completed([ex.submit(fix, s) for s in FIXES]):
        try:
            print("FIXED", f.result())
        except Exception as e:
            print("FAIL", str(e)[:160])
