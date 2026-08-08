#!/usr/bin/env python3
"""Portrait QA regeneration pass (2026-08-08).

Same pattern as fix_portraits.py: PORTRAIT_STYLE + the creature's visual_hint +
an explicit anatomical spec that names exact counts. NEVER passes a reference
image — the shared dragon style-reference is what bled dragon anatomy into
several earlier renders.

Usage:
    python scripts/qa_portraits.py 1 stegosaurus therizinosaurus ...
    python scripts/qa_portraits.py 2 stegosaurus            # escalated wording
    python scripts/qa_portraits.py 3 --raw-only stegosaurus # render, don't ship

Attempt >= 2 appends ESCALATIONS[slug][attempt], which names the defect the
previous attempt actually had.
"""
import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from assetlib import PORTRAIT_STYLE, ROOT, finalize, generate

CREATURES = {x["slug"]: x for x in
             json.loads((ROOT / "data" / "source_creatures.json").read_text())}

FRAME = (" The complete creature — head, body, every limb and the whole tail — "
         "is fully inside the frame with generous empty margin on all four "
         "sides; nothing is cropped, cut off, or touching any edge. Nothing "
         "else is in the picture: no second animal, no background creature, no "
         "silhouettes, no ghost shapes, no props fused to the body. "
         "Any open mouth shows teeth and a tongue inside, never a hollow void. "
         "Transparent background.")

REQS = {
    "stegosaurus":
        "Count the legs carefully: EXACTLY FOUR legs and no more — two short "
        "front legs under the shoulders and two tall back legs under the hips. "
        "There is no fifth leg and nothing leg-like under the middle of the "
        "belly. Exactly ONE head, ONE neck and ONE tail; the tail ends in four "
        "thagomizer spikes. Two alternating rows of broad diamond back plates.",
    "therizinosaurus":
        "Each hand bears EXACTLY THREE enormous scythe-like claws — three on "
        "the left hand and three on the right hand, six claws in total across "
        "the whole animal. Do not draw a fourth claw on either hand. "
        "Pot-bellied shaggy feathered dinosaur, long neck, small beaked head, "
        "exactly two legs and one tail.",
    "sarcosuchus":
        "EXACTLY ONE head on one neck. A single armoured crocodile skull with "
        "one pair of eyes and one pair of jaws — there is no second head, no "
        "extra snout and no smaller crocodile anywhere in the picture. Four "
        "legs and one long armoured tail, whole body on a sunlit sandy bank.",
    "opabinia":
        "EXACTLY FIVE stalked eyes standing up on top of the head — count them: "
        "five mushroom-shaped eye stalks, not four. One long flexible clawed "
        "proboscis reaching forward from the front of the head. Small "
        "amber-and-teal segmented swimmer with a row of side flaps and a "
        "fan-shaped tail, shown whole from the side.",
    "cyclops":
        "A giant HUMANOID: bare sun-cracked grey-brown human-like skin, two "
        "arms, two legs, a single large amber eye in the middle of the "
        "forehead. Absolutely NO TAIL of any kind, no scales, no reptile or "
        "lizard features, no lava, no fire, no fins, no spines. He is a "
        "muscular one-eyed man-shaped giant hefting a boulder, not a monster "
        "or a kaiju.",
    "dire-wolf":
        "ONE single wolf alone. Exactly one head, four legs and one bushy "
        "tail. There are NO other wolves — no pack, no companions, no dark "
        "shapes, silhouettes or ghost heads behind or around it. Smoky "
        "grey-brown coat with a heavy ruff, breath steaming.",
    "kitsune":
        "ONE snow-white fox with EXACTLY ONE HEAD and nine tails fanned behind "
        "it. There are absolutely NO extra fox heads, no spirit foxes, no "
        "ghostly duplicates and no floating faces anywhere in the picture — "
        "one animal only. Four legs. Standing side-on in full view, the nine "
        "pale-blue glowing tails spread wide behind it.",
    "unicorn":
        "A pearl-white horse with four legs, one flowing tail, one flowing "
        "mane and a single iridescent spiral horn. Nothing else is attached to "
        "it or near it: no serpent, no dragon, no vines, no green scaled "
        "shape, no creature coiled around its legs. Clean simple hooves.",
    "leviathan":
        "Show the WHOLE animal from snout to tail tip at a distance, small in "
        "the frame — not a close-up bust. A colossal barnacled blue-black "
        "plated sea beast with a complete visible body: blunt whale-like head, "
        "long ridged spine, two broad flippers and a full tail that ends in a "
        "clear tail fluke. It is a giant sea creature, NOT a dragon: no horns, "
        "no wings, no dragon spikes, no long fanged reptile snout. The entire "
        "silhouette is solid and readable; no part of it dissolves into water "
        "or spray.",
    "mosasaurus":
        "Show the WHOLE animal side-on from snout to tail tip, small in the "
        "frame — not a close-up head. A complete marine reptile: long "
        "crocodile-like jaws, streamlined body, four paddle flippers and a "
        "full tail ending in a two-lobed tail fin. Deep indigo back fading to "
        "a silver belly. The whole body is solid and opaque; nothing fades "
        "out, dissolves or disappears into water.",
}

ESCALATIONS = {  # {slug: {attempt: "..."}} — names the defect the last try had
    "opabinia": {
        2: "The previous attempt drew only FOUR eye stalks. That is wrong. "
           "Count them out as you draw: one, two, three, four, FIVE — five "
           "separate ball-tipped eye stalks rising in a row from the top of "
           "the head, so a viewer can count five of them.",
        3: "Two previous attempts drew only four eye stalks. Draw FIVE eye "
           "stalks: a central one flanked by two on the left and two on the "
           "right. Five in total, clearly separated, none hidden or merged.",
    },
}


def build_prompt(slug: str, attempt: int) -> str:
    c = CREATURES[slug]
    esc = ESCALATIONS.get(slug, {}).get(attempt, "")
    return (PORTRAIT_STYLE
            + "Creature: " + c["name"] + ". " + c["visual_hint"] + ". "
            + "CRITICAL anatomical requirements: " + REQS[slug] + " "
            + (esc + " " if esc else "")
            + FRAME)


def run(slug: str, attempt: int, ship: bool) -> str:
    prompt = build_prompt(slug, attempt)
    p = generate(prompt, f"part_{slug}_qa{attempt}", size="1024x1024",
                 transparent=True)
    if ship:
        finalize(p, f"parts/{slug}", 1024, 1024, margin=0.06)
        return f"{slug} (shipped, attempt {attempt})"
    return f"{slug} (raw only, attempt {attempt}) -> {p}"


def main() -> int:
    args = [a for a in sys.argv[1:]]
    ship = "--raw-only" not in args
    args = [a for a in args if a != "--raw-only"]
    attempt = int(args[0])
    slugs = args[1:] or sorted(REQS)
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(run, s, attempt, ship): s for s in slugs}
        for f in cf.as_completed(futs):
            try:
                print("OK  ", f.result())
            except Exception as e:  # noqa: BLE001
                print("FAIL", futs[f], str(e)[:200])
    print(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
