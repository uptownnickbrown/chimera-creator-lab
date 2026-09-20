#!/usr/bin/env python3
"""Normalize the committed part portraits to TIGHT alpha crops (2026-09-20).

Why: every portrait shipped as a 1024x1024 square with the creature centred
inside it. A wide creature therefore floated mid-square with empty rows above
and below, a tall one filled the square edge to edge, and the Fusion Lab rail
read as a row of creatures at different heights, some kissing the card edge.
CSS cannot see transparent padding, so the fix lives in the asset: trim each
portrait to its own alpha bounding box (any aspect ratio) and let each UI
context anchor the creature itself — cards on one ground line, orbits centred.

Same function as the runtime save path (backend/app/services/images.py
normalize_portrait) so summoned portraits and curated ones match exactly.

Usage:
    .venv/bin/python scripts/normalize_portraits.py            # in place
    .venv/bin/python scripts/normalize_portraits.py --dry-run  # report only
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.services.images import normalize_portrait  # noqa: E402

PARTS = ROOT / "frontend" / "public" / "assets" / "parts"


def main(dry_run: bool) -> None:
    files = sorted(PARTS.glob("*.webp"))
    before = after = 0
    for path in files:
        raw = path.read_bytes()
        src = Image.open(io.BytesIO(raw))
        out = normalize_portrait(raw)
        dst = Image.open(io.BytesIO(out))
        before += len(raw)
        after += len(out)
        print(f"{path.name:36} {src.size[0]}x{src.size[1]} -> {dst.size[0]}x{dst.size[1]}"
              f"  {len(raw) // 1024:4d}KB -> {len(out) // 1024:4d}KB")
        if not dry_run:
            path.write_bytes(out)
    print(f"\n{len(files)} portraits: {before // 1024}KB -> {after // 1024}KB"
          + ("  (dry run, nothing written)" if dry_run else ""))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)
