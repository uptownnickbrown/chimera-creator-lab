#!/usr/bin/env python3
"""Generate every remaining asset slot in docs/ASSET_WISHLIST.md.

Resumable: any slot whose finished PNG already exists under
frontend/public/assets/ is skipped unless --force is passed.

Usage
-----
    python scripts/generate_assets.py                 # every family, in order
    python scripts/generate_assets.py parts           # one family
    python scripts/generate_assets.py icons --only icons/stat_power
    python scripts/generate_assets.py parts --only parts/wolf --force
    python scripts/generate_assets.py env --contact   # rebuild contact sheet only

The five approved style anchors (lab/background, lab/platform,
lab/fusion_chamber, env/storm-coast, parts/dragon) are NEVER regenerated —
they exist on disk and act as images.edit references for their families.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from assetlib import (
    OUT_DIR,
    PORTRAIT_STYLE,
    RAW_DIR,
    ROOT,
    STYLE,
    finalize,
    finalize_opaque,
    generate,
)

MAX_WORKERS = 6

ENVS = json.loads((ROOT / "data" / "environments.json").read_text())
PARTS = json.loads((ROOT / "data" / "source_creatures.json").read_text())

# ---------------------------------------------------------------- anchors ---
REF_PART = RAW_DIR / "part_dragon.png"
REF_ENV = RAW_DIR / "env_storm-coast.png"
REF_PLATFORM = RAW_DIR / "lab_platform.png"
REF_BACKGROUND = RAW_DIR / "lab_background.png"
REF_ICON = RAW_DIR / "icon_stat_power.png"       # produced by this script
REF_TROPHY = RAW_DIR / "trophy_champion_cup.png"  # produced by this script
REF_AVATAR = RAW_DIR / "avatar_henry_a.png"       # produced by this script

NO_PROPS = "No trophies, no statues, no gold objects, no creatures. "

# Portraits kept drifting into painted mini-scenes (snow fields, waves, lava
# pools, cloud banks) instead of clean cutouts. This is appended to every
# source-part prompt.
PORTRAIT_ISOLATION = (
    " CRITICAL: this is a cut-out sprite of the creature ALONE. Do not paint "
    "any scenery, environment, habitat, ground, floor, terrain, rock, water, "
    "waves, snow, lava, sand, clouds, sky, mist, smoke, dust, moon, or cast "
    "shadow. No base, no platform, no pedestal, no rectangular backdrop panel, "
    "no vignette. Everything that is not the creature's own body must be "
    "completely empty and fully transparent, right up to its silhouette. "
    "Effects like fire or lightning are allowed only where they touch the "
    "creature's own body. Transparent background."
)

ICON_STYLE = (
    "Bold glowing holographic sigil icon for a game interface. A single SOLID "
    "FILLED silhouette shape built from thick chunky simple forms — absolutely "
    "no thin lines, no wireframe, no outline-only line art, no hairline "
    "strokes. Rendered in brilliant saturated electric cyan with a white-hot "
    "core and a soft cyan bloom, like a heavy neon glyph. Flat-ish emblem, not "
    "a scene, no perspective, no background, no frame, no border, no text, no "
    "letters, no numbers. Very high contrast, big and chunky, fills the frame, "
    "centered, must still read instantly when shrunk to 28 pixels. Transparent "
    "background. Subject: "
)


# ------------------------------------------------------------------- jobs ---
@dataclass
class Job:
    slot: str                 # e.g. "parts/wolf" -> assets/parts/wolf.webp
    raw: str                  # raw render basename in scripts/raw/
    prompt: str
    size: str = "1024x1024"
    transparent: bool = True
    references: tuple = ()
    # finalize spec: list of (slot, w, h, kwargs)
    outputs: list = field(default_factory=list)

    def targets(self) -> list[Path]:
        return [OUT_DIR / f"{s}.webp" for s, *_ in self.outputs]

    def done(self) -> bool:
        return all(p.exists() for p in self.targets())

    def run(self) -> str:
        refs = [str(r) for r in self.references if Path(r).exists()]
        raw = generate(self.prompt, self.raw, size=self.size,
                       transparent=self.transparent, references=refs)
        for slot, w, h, kw in self.outputs:
            if self.transparent:
                finalize(raw, slot, w, h, **kw)
            else:
                finalize_opaque(raw, slot, w, h)
        return self.slot


def cutout(slot, raw, prompt, size="1024x1024", refs=(), out=None, **fkw) -> Job:
    w, h = (int(x) for x in (out or size).split("x"))
    return Job(slot, raw, prompt, size=size, transparent=True, references=refs,
               outputs=[(slot, w, h, fkw)])


# --------------------------------------------------------------- families ---
# A few visual_hints in the data describe the animal hidden in its habitat
# ("only eyes above the surface"). That is great flavour text but useless as a
# fusion-part portrait, so the hint is rewritten for these slugs only.
HINT_OVERRIDES = {
    "saltwater-crocodile":
        "olive-black scaled hide beaded with glistening water, massive "
        "armoured tail and enormous toothy jaws held open, the whole animal "
        "out in the open in full view",
    "spinosaurus":
        "wet slate-blue and cream hide, tall red-striped sail along its back, "
        "long crocodilian jaws, standing upright in full view",
    "hydra":
        "bog-green scaled bulk, nine dripping serpentine necks fanned out and "
        "rearing high, acid steaming from the jaws, whole body in full view",
    "megalodon":
        "colossal shark, leaden grey back and white belly, jaws gaping to show "
        "rows of triangular teeth, entire body in full view",
}


def family_parts() -> list[Job]:
    jobs = []
    for c in PARTS:
        if c["slug"] == "dragon":
            continue  # approved anchor
        extra = ""
        if c.get("category") == "mythic":
            power = (c.get("traits") or {}).get("mythic_power")
            if power:
                extra = (f" Show its legendary power visibly in the pose and "
                         f"effects: {power}.")
        hint = HINT_OVERRIDES.get(c["slug"], c["visual_hint"])
        prompt = (PORTRAIT_STYLE + "Creature: " + c["name"] + ". " + hint +
                  "." + extra + PORTRAIT_ISOLATION)
        jobs.append(cutout(f"parts/{c['slug']}", f"part_{c['slug']}", prompt,
                           refs=(REF_PART,)))
    return jobs


def family_env() -> list[Job]:
    jobs = []
    for e in ENVS:
        if e["slug"] == "storm-coast":
            continue  # approved anchor
        prompt = (STYLE + "Wide establishing shot of an epic monster battle "
                  "arena, no creatures present, dramatic depth, open space at "
                  "center for two large combatants. " + NO_PROPS +
                  "Scene: " + e["visual_hint"])
        jobs.append(Job(
            slot=f"env/{e['slug']}", raw=f"env_{e['slug']}", prompt=prompt,
            size="1536x1024", transparent=False, references=(REF_ENV,),
            outputs=[(f"env/{e['slug']}", 1536, 1024, {}),
                     (f"env/{e['slug']}_card", 640, 360, {})]))
    return jobs


def family_lab() -> list[Job]:
    return [
        Job(slot="lab/platform_gold", raw="lab_platform_gold",
            prompt=STYLE + "A large empty champion display platform seen from "
            "slightly above and in front: a wide circular dark glass base with "
            "concentric rings of radiant GOLD light, a soft column of rising "
            "golden light particles above it, warm gold energy filigree around "
            "the rim, a few violet sparks. Isolated object on transparent "
            "background, nothing else, no creatures, no trophies.",
            size="1536x1024", transparent=True, references=(REF_PLATFORM,),
            outputs=[("lab/platform_gold", 1536, 640, {"margin": 0.02})]),

        Job(slot="lab/background_arena", raw="lab_background_arena",
            prompt=STYLE + "Wide interior establishing shot of a vast dark "
            "sci-fi battle arena bowl seen from the floor: tiers of distant "
            "spectator lights receding into bokeh like a crowd of tiny cyan "
            "and violet glows, sweeping holographic light beams, banners of "
            "energy, haze in the air. Empty floor center stage, no creatures, "
            "no people, no trophies. Dark enough that bright UI panels sit on "
            "top of it legibly. Energetic, premium, epic.",
            size="1536x1024", transparent=False, references=(REF_BACKGROUND,),
            outputs=[("lab/background_arena", 1920, 1080, {})]),

        cutout("ui/slot_empty", "ui_slot_empty",
               STYLE + "An empty fusion socket for a creature part: a dark "
               "octagonal brushed-metal receptacle with a recessed black glass "
               "center, faint violet standby glow pulsing inside, and a "
               "delicate spiral of thin cyan circuit-trace filigree with small "
               "node dots winding inward across the empty glass. Absolutely no "
               "question mark, no punctuation, no letters, no numbers, no "
               "symbols of any kind — only abstract circuit lines. Isolated "
               "object on transparent background, nothing else.",
               size="1024x1024", out="512x512", margin=0.02),

        Job(slot="ui/btn_create", raw="ui_btn_create",
            prompt=STYLE + "A wide horizontal sci-fi button plate for a game "
            "interface: a beveled dark brushed-metal frame with chamfered "
            "corners around a glowing violet-purple energy core, cyan edge "
            "highlights and small indicator lights, subtle circuit etching. "
            "Completely blank face — no text, no letters, no numbers, no "
            "symbols, no icon. Wide flat plate roughly three times as wide as "
            "it is tall. Isolated object on transparent background.",
            size="1536x1024", transparent=True, references=(),
            outputs=[("ui/btn_create", 1024, 320,
                      {"margin": 0.02, "alpha_thresh": 12})]),

        cutout("lab/mascot", "lab_mascot",
               STYLE + "A small friendly hovering laboratory assistant drone: "
               "rounded white-and-dark-navy chassis, one big glowing cyan lens "
               "eye, little floating antigravity rings, tiny articulated arms, "
               "soft cyan glow underneath, cheerful and cute but rendered in "
               "the same premium cinematic style. Not scary, no face beyond "
               "the lens. Isolated object on transparent background.",
               size="1024x1024", out="512x512"),
    ]


ENV_ICON_SUBJECTS = {
    "wave": "a single cresting curling ocean wave",
    "lightning": "a single jagged lightning bolt",
    "depth": "three very thick solid stacked downward-pointing chevron "
             "arrows descending, the largest at the top, heavy and bold",
    "dark": "a bold solid crescent moon with three small four-pointed stars "
            "beside it",
    "fire": "a single stylised flame",
    "smoke": "a curling plume of smoke rising",
    "leaf": "a single broad tropical leaf",
    "cliff": "a steep angular cliff face with a sheer vertical drop",
    "snow": "a single six-armed snowflake",
    "wind": "three swirling curved wind streak lines",
    "cloud": "a single big puffy cloud shape, completely solid and filled in, "
             "no hollow interior",
    "sun": "a blazing sun disc with radiating rays",
    "ruins": "a broken toppled classical stone column with a fallen capital",
    "mud": "a thick bubbling mud puddle with rising bubbles",
    "mist": "three horizontal drifting fog bands",
    "crane": "a harbour gantry crane silhouette with a hanging hook",
    "water": "a single large water droplet",
}


def family_icons() -> list[Job]:
    stats = {
        "stat_power": "a clenched armored fist striking with an impact burst "
                      "behind it",
        "stat_speed": "a forward-leaning arrow chevron trailing three motion "
                      "speed streaks",
        "stat_armor": "a heraldic shield made of layered overlapping armor "
                      "plates",
        "stat_size": "a tall creature silhouette beside a short one with a "
                     "height measuring bar between them",
        "stat_special": "a radiant many-pointed starburst of energy",
    }
    cats = {
        "cat_mythic": "a coiled winged dragon sigil emblem",
        "cat_extinct": "a spiral ammonite fossil embedded in stone",
        "cat_living": "a leaf and an animal paw print merged into one emblem",
    }
    subjects = dict(stats)
    subjects.update(cats)
    subjects.update({f"env_{k}": v for k, v in ENV_ICON_SUBJECTS.items()})

    jobs = []
    for name, subject in subjects.items():
        refs = () if name == "stat_power" else (REF_ICON,)
        jobs.append(cutout(f"icons/{name}", f"icon_{name}",
                           ICON_STYLE + subject + ".",
                           size="1024x1024", out="256x256", refs=refs,
                           margin=0.06))
    # stat_power must come first — it anchors the rest.
    jobs.sort(key=lambda j: j.slot != "icons/stat_power")
    return jobs


def family_trophy() -> list[Job]:
    return [
        cutout("trophy/champion_cup", "trophy_champion_cup",
               STYLE + "A magnificent champion trophy cup: polished radiant "
               "gold with sci-fi facets and winged handles, a swirling "
               "violet-purple energy core glowing inside the bowl, cyan "
               "sparks rising, standing on a dark metal plinth. Isolated "
               "object on transparent background, nothing else.",
               size="1024x1024", out="1024x1024", margin=0.02),

        cutout("trophy/badge_champion", "trophy_badge_champion",
               STYLE + "A compact champion crest badge: a gold faceted shield "
               "medallion with a star at its center, small gold laurel sprigs "
               "at the sides, violet energy glowing behind it, cyan rim light. "
               "Blank face, no text, no letters, no numbers. Isolated object "
               "on transparent background.",
               size="1024x1024", out="512x512", refs=(REF_TROPHY,),
               margin=0.04),

        Job(slot="trophy/laurel", raw="trophy_laurel",
            prompt=STYLE + "A wide gold laurel wreath frame: two curved sprays "
            "of polished gold laurel leaves opening upward, meeting at a small "
            "gold clasp at the bottom, violet energy glow tracing the inner "
            "edge, cyan sparks. The center of the wreath is completely empty "
            "and transparent. No text, no letters, no numbers, no ribbon "
            "banner. Isolated object on transparent background.",
            size="1536x1024", transparent=True, references=(REF_TROPHY,),
            outputs=[("trophy/laurel", 1024, 512, {"margin": 0.02})]),

        Job(slot="trophy/confetti_sheet", raw="trophy_confetti_sheet",
            prompt=STYLE + "A scatter of celebration energy particles spread "
            "evenly across the whole frame: BIG BRIGHT four-pointed star "
            "glints and glowing orbs in vivid saturated gold and brilliant "
            "electric cyan, each with a strong luminous bloom, mixed with a "
            "few bold light streaks. Wide range of sizes, the largest roughly "
            "a tenth of the frame across, all of them intense and clearly "
            "visible, never faint or tiny grey dust. Generous empty space "
            "between particles. No confetti paper rectangles, no objects, no "
            "background, no text. Pure particles on a fully transparent "
            "background, edge to edge.",
            size="1024x1024", transparent=True, references=(),
            outputs=[("trophy/confetti_sheet", 1024, 1024,
                      {"trim": False, "margin": 0.0})]),

        cutout("hall/pedestal", "hall_pedestal",
               STYLE + "A grand hall-of-champions display pedestal: a tall "
               "hexagonal dark polished stone and brushed-metal column with "
               "gold inlay filigree, a flat empty display top, warm gold "
               "uplight washing up the sides, a soft violet energy glow at the "
               "base. Empty top, nothing standing on it, no trophy, no "
               "creature. Isolated object on transparent background.",
               size="1024x1024", out="1024x768", refs=(REF_TROPHY,),
               margin=0.03),
    ]


AVATAR_STYLE = (
    "Cinematic sci-fi game art character portrait for a kids game, same "
    "premium neon laboratory look: deep navy shadows, electric cyan and violet "
    "rim light. A friendly heroic eight-year-old boy scientist with fair skin, "
    "light brown hair and a warm confident smile, wearing a crisp white lab "
    "coat with glowing cyan trim and cyan-lensed goggles. Slightly "
    "kid-proportioned — a little larger head, big expressive eyes — but "
    "rendered with cinematic lighting and detail, never cartoonish flat "
    "vector, never scary. Full body, centered, not touching the image edges. "
    "Absolutely no text, letters, numbers or watermarks. Isolated character on "
    "a transparent background, nothing else. "
)


def family_avatar() -> list[Job]:
    variants = {
        "a": "Goggles pushed up on his forehead, short tousled light brown "
             "hair, standing confidently with hands on hips, chin up.",
        "b": "Goggles worn over his eyes with cyan lenses glowing, wavy "
             "shoulder-length light brown hair, one arm raised holding up a "
             "small glowing violet energy vial, leaning forward eagerly.",
        "c": "Goggles around his neck, curly light brown hair, arms folded "
             "across his chest, a holographic cyan clipboard hovering beside "
             "his shoulder, calm clever grin.",
    }
    jobs = []
    for k, pose in variants.items():
        refs = () if k == "a" else (REF_AVATAR,)
        jobs.append(cutout(f"avatar/henry_{k}", f"avatar_henry_{k}",
                           AVATAR_STYLE + pose, size="1024x1024",
                           out="512x512", refs=refs))
    jobs.sort(key=lambda j: j.slot != "avatar/henry_a")
    return jobs


FAMILIES: dict[str, Callable[[], list[Job]]] = {
    "parts": family_parts,
    "env": family_env,
    "lab": family_lab,
    "icons": family_icons,
    "trophy": family_trophy,
    "avatar": family_avatar,
}
# "avatar" is deliberately NOT in ORDER: Henry's avatars are made from real
# reference photos elsewhere. Run `generate_assets.py avatar` explicitly if a
# generic fallback avatar is ever needed again.
ORDER = ["lab", "icons", "env", "trophy", "parts"]


# ----------------------------------------------------------------- checks ---
def qa_alpha(path: Path) -> tuple[bool, str]:
    """Cutouts must carry a real alpha channel with plenty of empty space."""
    img = Image.open(path)
    if img.mode != "RGBA":
        return False, f"{path.name}: mode {img.mode}, no alpha"
    hist = img.getchannel("A").histogram()
    pct = 100.0 * hist[0] / (img.width * img.height)
    return pct > 15.0, f"{path.name}: {pct:.1f}% fully transparent"


# --------------------------------------------------------- contact sheets ---
def contact_sheet(family: str, thumb: int = 200) -> Path | None:
    jobs = FAMILIES[family]()
    slots = [s for j in jobs for s, *_ in j.outputs]
    # include the family's approved anchor for side-by-side comparison
    anchors = {"parts": ["parts/dragon"], "env": ["env/storm-coast"],
               "lab": ["lab/platform", "lab/background",
                       "lab/fusion_chamber"]}
    slots = anchors.get(family, []) + slots
    paths = [OUT_DIR / f"{s}.webp" for s in slots]
    paths = [p for p in paths if p.exists()]
    if not paths:
        return None
    cols = min(8, max(1, int(len(paths) ** 0.5 + 0.999)))
    cols = max(cols, 4)
    rows = (len(paths) + cols - 1) // cols
    pad = 6
    sheet = Image.new("RGB", (cols * (thumb + pad) + pad,
                              rows * (thumb + pad) + pad), (10, 14, 30))
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGBA")
        im.thumbnail((thumb, thumb), Image.LANCZOS)
        tile = Image.new("RGBA", (thumb, thumb), (10, 14, 30, 255))
        tile.paste(im, ((thumb - im.width) // 2, (thumb - im.height) // 2), im)
        x = pad + (i % cols) * (thumb + pad)
        y = pad + (i // cols) * (thumb + pad)
        sheet.paste(tile.convert("RGB"), (x, y))
    out = RAW_DIR / f"_contact_{family}.jpg"
    sheet.save(out, quality=88)
    print(f"contact sheet: {out}  ({len(paths)} tiles, {cols} cols)")
    return out


# ------------------------------------------------------------------- main ---
def run_jobs(jobs: list[Job], workers: int = MAX_WORKERS) -> list[str]:
    failures = []
    if not jobs:
        return failures
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(j.run): j for j in jobs}
        for f in cf.as_completed(futs):
            j = futs[f]
            try:
                f.result()
                print(f"OK   {j.slot}")
            except Exception as e:  # noqa: BLE001
                print(f"FAIL {j.slot}: {str(e)[:220]}")
                failures.append(f"{j.slot}: {str(e)[:220]}")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("family", nargs="?", default="all",
                    choices=["all", *FAMILIES])
    ap.add_argument("--only", action="append", default=[],
                    help="slot name (e.g. parts/wolf); repeatable")
    ap.add_argument("--force", action="store_true",
                    help="regenerate even if the finished PNG exists")
    ap.add_argument("--first", action="store_true",
                    help="run only the first pending job of the family (QA)")
    ap.add_argument("--limit", type=int, default=0,
                    help="run at most N pending jobs, then stop (mid-batch "
                         "checkpoint: review the contact sheet, then re-run)")
    ap.add_argument("--contact", action="store_true",
                    help="only rebuild the contact sheet(s)")
    ap.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = ap.parse_args()

    fams = ORDER if args.family == "all" else [args.family]
    if args.contact:
        for fam in fams:
            contact_sheet(fam)
        return 0

    t0 = time.time()
    all_failures: dict[str, list[str]] = {}
    for fam in fams:
        jobs = FAMILIES[fam]()
        if args.only:
            jobs = [j for j in jobs if j.slot in args.only]
        if not args.force:
            jobs = [j for j in jobs if not j.done()]
        if args.first:
            jobs = jobs[:1]
        if args.limit:
            jobs = jobs[:args.limit]
        print(f"\n=== {fam}: {len(jobs)} job(s) ===")
        fails = run_jobs(jobs, args.workers)
        if fails:
            all_failures[fam] = fails
        contact_sheet(fam)

    print(f"\nwall time: {time.time() - t0:.0f}s")
    if all_failures:
        print("FAILURES:")
        for fam, fails in all_failures.items():
            for f in fails:
                print(f"  {fam}: {f}")
        return 1
    print("all requested slots complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
