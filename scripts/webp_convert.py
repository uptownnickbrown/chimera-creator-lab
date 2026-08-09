"""One-time transcode of every committed/on-disk PNG to WebP.

The runtime already writes WebP (services/images.py); this catches everything
that was painted before that switch:

  * frontend/public/assets — 234 painted PNGs, ~231MB, baked into the Docker
    image. Renamed outright: nothing records these paths in a database, so the
    .png files go away and the code references .webp.
  * media/ — the player's generated heroes, thumbs, part portraits and finals
    key art, ~121MB. Renamed AND the database paths that point at them are
    rewritten in the same run, so the two can never disagree.
  * data/seed — the committed starter crew's hero/thumb art.

Quality is q90 / method 6 — the same constants the runtime uses
(app/services/images.py WEBP_QUALITY / WEBP_METHOD), measured at ~90% smaller
with alpha intact and no visible difference at 1:1. Alpha is preserved exactly
when the source has it; opaque art is written as RGB.

Every conversion is verified before the PNG is removed: the WebP must reopen,
match the source's size and alpha presence, and be smaller. Anything that
fails verification keeps its PNG and is reported.

Usage:
    python scripts/webp_convert.py --dry-run
    python scripts/webp_convert.py --assets --seed
    python scripts/webp_convert.py --media --db chimera.db
    python scripts/webp_convert.py --all --db chimera.db

--db is required for --media and has no default: this rewrites database rows.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

QUALITY = 90
METHOD = 6

ASSETS = REPO / "frontend" / "public" / "assets"
MEDIA = REPO / "media"
SEED = REPO / "data" / "seed"


def convert(png: Path) -> tuple[Path | None, str]:
    """Write `png` beside itself as .webp and verify it. Returns (path, note)."""
    from PIL import Image

    webp = png.with_suffix(".webp")
    src = Image.open(png)
    has_alpha = src.mode in ("RGBA", "LA") or "transparency" in src.info
    src.load()
    out = src.convert("RGBA" if has_alpha else "RGB")
    out.save(webp, "WEBP", quality=QUALITY, method=METHOD)

    check = Image.open(webp)
    check.load()
    if check.size != src.size:
        return None, f"size drift {src.size} -> {check.size}"
    if has_alpha and check.mode != "RGBA":
        return None, f"alpha lost (mode {check.mode})"
    before, after = png.stat().st_size, webp.stat().st_size
    if after >= before:
        return None, f"grew ({before // 1024}KB -> {after // 1024}KB)"
    return webp, f"{before // 1024}KB -> {after // 1024}KB ({100 - after * 100 // before}% off)"


def convert_tree(root: Path, dry: bool, label: str) -> tuple[int, int, int, int]:
    """Convert every PNG under `root`. Returns (files, before, after, failures)."""
    pngs = sorted(p for p in root.rglob("*.png"))
    if not pngs:
        print(f"{label}: nothing to convert")
        return 0, 0, 0, 0

    before = sum(p.stat().st_size for p in pngs)
    print(f"{label}: {len(pngs)} PNG, {before // 1024 // 1024}MB")
    if dry:
        return len(pngs), before, 0, 0

    after = done = failed = 0
    for png in pngs:
        webp, note = convert(png)
        if webp is None:
            print(f"  ! {png.relative_to(REPO)}: {note} — keeping PNG")
            png.with_suffix(".webp").unlink(missing_ok=True)
            failed += 1
            continue
        after += webp.stat().st_size
        png.unlink()
        done += 1
    print(f"  {done} converted, {after // 1024 // 1024}MB "
          f"({100 - after * 100 // before}% off){f', {failed} FAILED' if failed else ''}")
    return len(pngs), before, after, failed


def repoint_database(db_path: Path, dry: bool) -> None:
    """Rewrite every stored /media/... .png path to .webp.

    Only paths whose WebP now exists on disk are touched, so a PNG that failed
    conversion keeps a row pointing at the file that is still there.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def landed(web_path: str) -> bool:
        """Does the .webp for this /media/... path actually exist?"""
        rel = web_path.removeprefix("/media/")
        return (MEDIA / rel).with_suffix(".webp").exists()

    updates: list[tuple[str, tuple]] = []

    for table, col in (("creatures", "hero_image_path"), ("creatures", "thumb_path"),
                       ("custom_parts", "art")):
        rows = conn.execute(
            f"select id, {col} as p from {table} where {col} like '%.png'"
        ).fetchall()
        for row in rows:
            if not landed(row["p"]):
                print(f"  ! {table}.{col} #{row['id']} -> {row['p']} has no WebP — left alone")
                continue
            updates.append((f"update {table} set {col} = ? where id = ?",
                            (row["p"][: -len(".png")] + ".webp", row["id"])))

    # Championship key art lives inside the bracket JSON blob, not a column.
    for row in conn.execute("select id, bracket from tournaments").fetchall():
        try:
            bracket = json.loads(row["bracket"]) if row["bracket"] else None
        except (TypeError, json.JSONDecodeError):
            continue
        art = (bracket or {}).get("final_art")
        if not (isinstance(art, str) and art.endswith(".png")):
            continue
        if not landed(art):
            print(f"  ! tournaments #{row['id']} final_art {art} has no WebP — left alone")
            continue
        bracket["final_art"] = art[: -len(".png")] + ".webp"
        updates.append(("update tournaments set bracket = ? where id = ?",
                        (json.dumps(bracket), row["id"])))

    print(f"database: {len(updates)} path(s) to repoint in {db_path}")
    if dry or not updates:
        conn.close()
        return
    for sql, params in updates:
        conn.execute(sql, params)
    conn.commit()
    conn.close()
    print(f"  {len(updates)} row(s) repointed")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assets", action="store_true", help="frontend/public/assets")
    ap.add_argument("--media", action="store_true", help="media/ + database paths")
    ap.add_argument("--seed", action="store_true", help="data/seed")
    ap.add_argument("--all", action="store_true", help="all three")
    ap.add_argument("--db", help="SQLite path; required with --media")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    do_assets = args.assets or args.all
    do_media = args.media or args.all
    do_seed = args.seed or args.all
    if not (do_assets or do_media or do_seed):
        ap.error("pick at least one of --assets / --media / --seed / --all")
    if do_media and not args.db:
        ap.error("--media rewrites database rows: pass --db explicitly")
    if do_media and not Path(args.db).exists():
        ap.error(f"--db {args.db} does not exist")

    total_before = total_after = failures = 0
    for enabled, root, label in ((do_assets, ASSETS, "assets"),
                                 (do_seed, SEED, "seed"),
                                 (do_media, MEDIA, "media")):
        if not enabled:
            continue
        _, before, after, failed = convert_tree(root, args.dry_run, label)
        total_before += before
        total_after += after
        failures += failed

    if do_media:
        repoint_database(Path(args.db), args.dry_run)

    if not args.dry_run and total_before:
        print(f"\ntotal: {total_before // 1024 // 1024}MB -> "
              f"{total_after // 1024 // 1024}MB "
              f"({100 - total_after * 100 // total_before}% off)")
    if failures:
        print(f"{failures} file(s) failed verification and kept their PNG")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
