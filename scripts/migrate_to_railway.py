#!/usr/bin/env python
"""One-time bootstrap: copy the local SQLite game into Railway's Postgres.

Henry has ~30 chimeras he loves, ~100 cached battles, and a shelf of tournament
champions. Losing any of it is not acceptable, and neither is renumbering it:

  * `media/creatures/<id>.png` and `<id>_thumb.png` are named after creature ids
  * `tournaments.bracket` / `entrant_ids` embed creature ids
  * `battles.canonical_key` is "minId:maxId:environment"

So primary keys are copied EXACTLY, never regenerated. Postgres sequences are
then fast-forwarded to max(id)+1 — the classic bug in this kind of migration is
skipping that step, after which the very next creature Henry makes collides with
id=1 and the insert blows up.

Usage
-----
    # look before you leap
    .venv/bin/python scripts/migrate_to_railway.py \\
        --sqlite ./chimera.db --target "$RAILWAY_PG_PUBLIC_URL" --dry-run

    # the real thing (target must be empty, or pass --force to wipe first)
    .venv/bin/python scripts/migrate_to_railway.py \\
        --sqlite ./chimera.db --target "$RAILWAY_PG_PUBLIC_URL"

The target schema must already exist (`alembic upgrade head`, which the app
container runs on boot). This script never creates or alters tables.

Media is NOT handled here — it goes up with the Railway CLI:
    railway volume files upload ./media /data/media --overwrite
See docs/DEPLOY.md.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from datetime import UTC

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.config import _normalize_db_url
from app.db import Base
from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import create_async_engine

# Dependency order: parents first (creatures before battles/tournaments).
TABLES = list(Base.metadata.sorted_tables)
CHUNK = 500


# -- helpers ------------------------------------------------------------------

def _sqlite_url(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"no SQLite database at {path}")
    return f"sqlite+aiosqlite:///{path}"


def _target_url(url: str) -> str:
    """Accept whatever Railway hands you (postgres://, postgresql://) and make
    it an asyncpg URL. Refuse SQLite: this script only ever writes Postgres."""
    normalized = _normalize_db_url(url)
    if not normalized.startswith("postgresql+asyncpg://"):
        raise SystemExit(f"--target must be a Postgres URL, got {url!r}")
    return normalized


def _redact(url: str) -> str:
    """Never print a password, not even into a terminal scrollback."""
    if "@" not in url:
        return url
    head, tail = url.split("@", 1)
    scheme, _, creds = head.partition("://")
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{tail}"


def _coerce_row(table, row: dict) -> dict:
    """SQLite hands back naive datetimes; Postgres `timestamptz` columns want
    tz-aware ones. Everything Henry's game stores is UTC, so say so explicitly
    rather than letting the driver guess."""

    out = dict(row)
    for col in table.columns:
        value = out.get(col.name)
        if hasattr(value, "tzinfo") and value.tzinfo is None:
            out[col.name] = value.replace(tzinfo=UTC)
    return out


async def _counts(conn, tables=TABLES) -> dict[str, int]:
    counts = {}
    for table in tables:
        counts[table.name] = (
            await conn.execute(select(func.count()).select_from(table))
        ).scalar_one()
    return counts


# -- the migration ------------------------------------------------------------

async def read_source(sqlite_path: Path) -> dict[str, list[dict]]:
    """Pull every model table out of the local game, in dependency order."""
    engine = create_async_engine(_sqlite_url(sqlite_path))
    try:
        async with engine.connect() as conn:
            data = {}
            for table in TABLES:
                result = await conn.execute(select(table))
                data[table.name] = [dict(r) for r in result.mappings()]
            return data
    finally:
        await engine.dispose()


async def migrate(sqlite_path: Path, target: str, *, dry_run: bool, force: bool) -> int:
    data = await read_source(sqlite_path)
    engine = create_async_engine(_target_url(target))
    try:
        async with engine.connect() as conn:
            existing = await _counts(conn)

        print(f"source : {sqlite_path}")
        print(f"target : {_redact(_target_url(target))}")
        print()
        print(f"{'table':<16}{'source':>8}{'target now':>12}{'next id':>10}")
        print("-" * 46)
        for table in TABLES:
            rows = data[table.name]
            pk = _pk_column(table)
            next_id = (max((r[pk.name] for r in rows), default=0) + 1) if pk is not None else "-"
            print(f"{table.name:<16}{len(rows):>8}{existing[table.name]:>12}{next_id:>10}")
        print()

        occupied = {name: n for name, n in existing.items() if n}
        if occupied and not force:
            raise SystemExit(
                "target is NOT empty: "
                + ", ".join(f"{k}={v}" for k, v in occupied.items())
                + "\nThis is normal on a fresh deploy — the app seeds a starter crew on"
                "\nfirst boot. Re-run with --force to delete those rows and replace them"
                "\nwith Henry's real game."
            )

        if dry_run:
            plan = "delete-then-insert" if occupied else "insert"
            print(f"DRY RUN — nothing written. Plan: {plan}, then reset sequences.")
            return 0

        async with engine.begin() as conn:
            if occupied:
                # Children first, so no FK ever dangles mid-wipe.
                for table in reversed(TABLES):
                    await conn.execute(table.delete())
                print("cleared existing rows")

            for table in TABLES:
                rows = data[table.name]
                if not rows:
                    continue
                payload = [_coerce_row(table, r) for r in rows]
                for start in range(0, len(payload), CHUNK):
                    await conn.execute(insert(table), payload[start : start + CHUNK])
                print(f"inserted {len(rows):>5} -> {table.name}")

            await reset_sequences(conn)

        async with engine.connect() as conn:
            after = await _counts(conn)
        bad = [t.name for t in TABLES if after[t.name] != len(data[t.name])]
        if bad:
            raise SystemExit(f"row-count mismatch after migration: {bad}")
        print("\nverified row counts match source for every table.")
        return 0
    finally:
        await engine.dispose()


def _pk_column(table):
    cols = list(table.primary_key.columns)
    return cols[0] if len(cols) == 1 else None


async def reset_sequences(conn) -> None:
    """Fast-forward every identity sequence past the ids we just forced in.

    Copying explicit primary keys does NOT advance the sequence backing them,
    so without this the next INSERT starts at 1 and trips the PK constraint.
    `setval(seq, max(id) + 1, false)` makes the *next* nextval() return
    max(id) + 1; the COALESCE keeps an empty table at 1.
    """
    for table in TABLES:
        pk = _pk_column(table)
        if pk is None:
            continue
        seq = (
            await conn.execute(
                text("SELECT pg_get_serial_sequence(:t, :c)"),
                {"t": table.name, "c": pk.name},
            )
        ).scalar()
        if not seq:  # no sequence (non-integer or externally managed key)
            continue
        next_id = (
            await conn.execute(
                text(
                    f"SELECT setval(:seq, COALESCE((SELECT MAX({pk.name}) FROM {table.name}), 0) + 1, false)"
                ),
                {"seq": seq},
            )
        ).scalar()
        print(f"sequence {seq} -> next {pk.name} = {next_id}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy the local SQLite game into Railway Postgres, ids intact."
    )
    parser.add_argument("--sqlite", required=True, type=Path, help="path to chimera.db")
    parser.add_argument(
        "--target", required=True,
        help="Postgres URL (Railway's DATABASE_PUBLIC_URL when running from your laptop)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    parser.add_argument(
        "--force", action="store_true",
        help="delete existing rows in the target first (e.g. the auto-seeded starter crew)",
    )
    args = parser.parse_args()
    return asyncio.run(
        migrate(args.sqlite.resolve(), args.target, dry_run=args.dry_run, force=args.force)
    )


if __name__ == "__main__":
    raise SystemExit(main())
