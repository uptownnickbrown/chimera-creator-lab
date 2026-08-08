#!/usr/bin/env python3
"""Generate Henry's avatar variants from real photos via images.edit likeness.

Photos provided by Nick in ~/Downloads/henry-pics/. Output: three stylized
game avatars (transparent) matching the approved lab art style.
"""

import concurrent.futures as cf
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from assetlib import finalize, generate

PICS = Path.home() / "Downloads" / "henry-pics"
FACE_REF = PICS / "IMG_2552.jpg"     # clearest smiling 3/4 face
FACE_REF2 = PICS / "IMG_7690.jpg"    # frontal face
POSE_REF = PICS / "IMG_7721.jpg"     # dynamic balancing pose he loves

BASE = (
    "Stylized hero avatar portrait for a cinematic neon sci-fi game, of the "
    "SAME BOY shown in the attached reference photos — keep his exact "
    "likeness: shaggy golden-blond hair with tousled fringe, fair skin, "
    "bright hazel-brown eyes, his confident warm grin. Age about 8. He wears "
    "a sleek white-and-navy junior scientist lab coat with glowing cyan trim "
    "and holographic goggles pushed up on his forehead. Premium game-art "
    "rendering (painterly realistic, kid-friendly proportions, NOT cartoon "
    "chibi), dramatic cyan and violet lab rim-lighting. Full body, centered, "
    "not touching image edges, transparent background. No text or watermarks. "
)

POSES = {
    "henry_a": "Pose: standing tall facing three-quarter view, arms crossed, "
               "confident builder-genius smile.",
    "henry_b": "Pose: mid-celebration, one fist punching up, laughing with joy, "
               "sparks of violet fusion energy around his fist.",
    "henry_c": "Pose: dynamic action lean — balancing mid-stride on a glowing "
               "platform edge like a parkour hero (inspired by the balancing "
               "pose in the reference photos), arms out, grinning at the viewer.",
}


def gen(slot, pose):
    refs = [str(FACE_REF), str(FACE_REF2)]
    if slot == "henry_c":
        refs.append(str(POSE_REF))
    p = generate(BASE + pose, f"avatar_{slot}", size="1024x1024",
                 transparent=True, references=refs)
    finalize(p, f"avatar/{slot}", 512, 512)


if __name__ == "__main__":
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(gen, s, p): s for s, p in POSES.items()}
        for f in cf.as_completed(futs):
            s = futs[f]
            try:
                f.result()
                print("DONE", s)
            except Exception as e:
                print("FAIL", s, str(e)[:200])
