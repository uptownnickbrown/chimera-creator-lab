"""Repaint hero art that was destroyed, using a screenshot of the original.

WHAT HAPPENED (2026-08-09): `media/` lives at the repo root and is shared by
every checkout, but the SQLite path is relative to the process's working
directory. A QA run booted against an EMPTY database, the first-run starter
seeder fired, and it copied its eight pregenerated heroes over
media/creatures/1..8.png — the files belonging to seven of Henry's creatures.
The database rows were untouched: names, stats, win/loss history, and
championships all survived. Only the pixels were lost.

WHAT THIS DOES: the QA screenshot sweeps in qa/ were captured BEFORE the
overwrite, so each lost creature still exists as a clean, full-body crop.
Those crops go to gpt-image-1.5 `images.edit` together with the creature's
own stored visual_spec — the exact text that produced the original art — and
it repaints a full-resolution transparent hero of the same design. Not the
original bytes; the same creature.

The result is written through the SAME pipeline the runtime uses
(images._thumb_from_hero_bytes), so hero and thumb stay consistent with every
other creature in the Codex.

Usage:
    python scripts/recover_heroes.py --db chimera.db --dry-run
    python scripts/recover_heroes.py --db chimera.db --ids 5
    python scripts/recover_heroes.py --db chimera.db          # all seven

--db is required and has no default: this script overwrites art, and it must
never be possible to point it at the live game by forgetting a flag.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

# The pre-overwrite references, best first. The codex tile is a clean, complete,
# well-isolated full-body view of every creature; where a screenshot also caught
# one at hero size, that goes first for the extra detail.
REFERENCES: dict[int, list[str]] = {
    1: ["qa/fusionwait/reveal_desktop.png:470,300,1800,930",
        "qa/fusionwait/codex_desktop.png:1700,765,2030,1035"],
    2: ["qa/fusionwait/codex_desktop.png:1350,765,1680,1035"],
    3: ["qa/fusionwait/codex_desktop.png:1000,765,1330,1035"],
    5: ["qa/fusionwait/codex_desktop.png:650,765,980,1035"],
    6: ["qa/fusionwait/codex_desktop.png:1700,355,2030,625"],
    7: ["qa/fusionwait/codex_desktop.png:1350,355,1680,625"],
    8: ["qa/rebuild2/codex_desktop.png:2120,420,2760,830",
        "qa/fusionwait/codex_desktop.png:1000,355,1330,625"],
}

# Appended to the standard hero prompt. The reference is a small screenshot
# crop of a UI card, so the model must be told to read the DESIGN off it and
# ignore everything about how it was framed.
MATCH_REFERENCE = (
    " CRITICAL: the attached image(s) show THIS EXACT CREATURE as it was "
    "previously painted. Reproduce that same creature faithfully — the same "
    "silhouette, body plan, anatomy, markings, colour palette, and signature "
    "features. Do not redesign it, do not restyle it, do not add or remove "
    "limbs, wings, tails, horns, or plates. The reference is a low-resolution "
    "crop from a screenshot: repaint it at full resolution with crisp detail, "
    "and ignore the card background, UI panel, glow, and any platform or "
    "pedestal it was sitting on. Match the reference's pose and facing "
    "direction. Output the creature alone on a fully transparent background."
)


def crop_spec(spec: str):
    """"path/to.png:x0,y0,x1,y1" -> (Path, box) with the box optional."""
    if ":" in spec and spec.rsplit(":", 1)[1].count(",") == 3:
        path, box = spec.rsplit(":", 1)
        return REPO / path, tuple(int(v) for v in box.split(","))
    return REPO / spec, None


def load_references(specs: list[str]) -> list[bytes]:
    from PIL import Image

    out = []
    for spec in specs:
        path, box = crop_spec(spec)
        if not path.exists():
            print(f"    ! reference missing: {path}")
            continue
        img = Image.open(path).convert("RGB")
        if box:
            img = img.crop(box)
        # Upscale the crop: the model reads a 1024px reference far better than
        # a 330px one, and LANCZOS keeps the design legible.
        if img.width < 1024:
            img = img.resize((1024, round(1024 * img.height / img.width)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        out.append(buf.getvalue())
    return out


async def repaint(cid: int, name: str, visual_spec: str, refs: list[bytes],
                  media: Path) -> bool:
    from app.services import ai, images

    prompt = images.HERO_STYLE + (visual_spec or name) + MATCH_REFERENCE
    files = [(f"ref{i}.png", b, "image/png") for i, b in enumerate(refs)]

    # input_fidelity="high" is what makes an edit hold the reference's design
    # instead of drifting; if the endpoint ever stops taking it, the repaint is
    # still worth doing without it.
    extras: dict = {"input_fidelity": "high"}
    for attempt, quality in enumerate(("high", "high", "medium"), 1):
        try:
            resp = await ai.client().images.edit(
                model=ai.IMAGE_MODEL,
                image=[(n, b, m) for n, b, m in files],
                prompt=prompt,
                size=images.HERO_SIZE,
                quality=quality,
                background="transparent",
                **extras,
            )
            png = base64.b64decode(resp.data[0].b64_json)
        except Exception as exc:  # noqa: BLE001 - API errors: report and retry
            msg = str(exc)
            print(f"    attempt {attempt} ({quality}) failed: {msg[:180]}")
            if extras and "input_fidelity" in msg:
                print("    (retrying without input_fidelity)")
                extras = {}
            await asyncio.sleep(3 * attempt)
            continue

        # Written through the runtime's format, not the API's: heroes on disk
        # are WebP, and the stored hero_image_path points at the WebP.
        (media / f"{cid}{images.MEDIA_EXT}").write_bytes(images.to_webp(png))
        (media / f"{cid}_thumb{images.MEDIA_EXT}").write_bytes(
            images._thumb_from_hero_bytes(png))
        print(f"    repainted {name} ({quality}, attempt {attempt}, {len(png)//1024}KB)")
        return True
    return False


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="path to the SQLite database")
    ap.add_argument("--media", default=str(REPO / "media" / "creatures"))
    ap.add_argument("--ids", help="comma-separated subset; default is all seven")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ids = ([int(v) for v in args.ids.split(",")] if args.ids
           else sorted(REFERENCES))
    media = Path(args.media)
    conn = sqlite3.connect(args.db)
    placeholders = ",".join("?" * len(ids))
    rows = {r[0]: r for r in conn.execute(
        f"select id, name, visual_spec from creatures where id in ({placeholders})", ids)}

    print(f"database : {args.db}")
    print(f"media    : {media}")
    for cid in ids:
        if cid not in rows:
            print(f"  {cid}: NOT IN DATABASE — skipping")
            continue
        _, name, spec = rows[cid]
        print(f"  {cid}: {name} <- {', '.join(REFERENCES.get(cid, []))}")
        print(f"      spec: {(spec or '')[:110]}...")
    if args.dry_run:
        print("\ndry run — nothing written")
        return 0

    if not os.environ.get("OPEN_AI_API_KEY"):
        env = REPO / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("OPEN_AI_API_KEY="):
                    os.environ["OPEN_AI_API_KEY"] = line.split("=", 1)[1].strip()
    if not os.environ.get("OPEN_AI_API_KEY"):
        print("no OPEN_AI_API_KEY — refusing to run")
        return 2

    # The current files are wrong, but they are still the only thing standing
    # between the Codex and a blank card. Keep them until a repaint lands.
    backup = media.parent / f"_pre_recovery_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}"
    backup.mkdir(parents=True, exist_ok=True)
    for cid in ids:
        for suffix in (".png", "_thumb.png", ".webp", "_thumb.webp"):
            src = media / f"{cid}{suffix}"
            if src.exists():
                shutil.copy2(src, backup / src.name)
    print(f"backup   : {backup}\n")

    ok, failed = [], []
    for cid in ids:
        if cid not in rows:
            continue
        _, name, spec = rows[cid]
        print(f"  {cid} {name}")
        refs = load_references(REFERENCES.get(cid, []))
        if not refs:
            print("    ! no usable reference — skipping")
            failed.append(cid)
            continue
        (ok if await repaint(cid, name, spec, refs, media) else failed).append(cid)

    print(f"\nrepainted {len(ok)}: {ok}")
    if failed:
        print(f"FAILED {len(failed)}: {failed} — originals still in {backup}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
