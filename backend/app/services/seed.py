"""First-run starter crew (data/seed, built by scripts/gen_seed_creatures.py).

A brand-new player should open the app to a living Codex and one full
8-entrant tournament bracket, not an empty lab. On boot, if the creatures
table has ZERO rows and the committed seed pack exists, the 8 pregenerated
chimeras are inserted as complete creatures and their art is copied into the
media dir under the exact names the runtime uses ({id} / {id}_thumb, WebP).

Strictly first-run only: ANY existing creature row — even a failed one —
means the player has history and seeding is a no-op. A missing or broken
seed pack logs one line and never blocks boot.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Creature, ImageStatus, RecordStatus
from ..schemas import CreatureRecord

log = logging.getLogger("chimera.seed")


def _art(entry: Path, stem: str) -> Path | None:
    """A seed entry's art file, WebP first then PNG, or None if absent."""
    for ext in (".webp", ".png"):
        path = entry / f"{stem}{ext}"
        if path.exists():
            return path
    return None


def _record_fields(record: CreatureRecord) -> dict:
    """CreatureRecord -> Creature column values (mirrors api/creatures.py)."""
    return {
        "name": record.name, "title": record.title, "rarity": record.rarity,
        "role": record.role, "core_stats": record.core_stats.model_dump(),
        "abilities": [a.model_dump() for a in record.abilities],
        "strengths": record.strengths, "weaknesses": record.weaknesses,
        "environment_affinities": record.environment_affinities.model_dump(),
        "sim_profile": record.sim_profile.model_dump(),
        "visual_spec": record.visual_spec, "anatomy_plan": record.anatomy_plan,
        "fun_fact": record.fun_fact,
    }


async def seed_if_empty(session: AsyncSession) -> int:
    """Insert the starter crew into an empty database. Returns rows created.

    Idempotent and boot-safe: any existing creature, a missing manifest, or a
    broken seed entry all degrade to a logged no-op — never a crash.
    """
    settings = get_settings()
    seed_dir = settings.data_dir / "seed"
    manifest_path = seed_dir / "manifest.json"

    existing = (
        await session.execute(select(func.count()).select_from(Creature))
    ).scalar_one()
    if existing:
        return 0

    if not manifest_path.exists():
        log.info("seed: no starter crew at %s — skipping", manifest_path)
        return 0
    try:
        keys = json.loads(manifest_path.read_text())["keys"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        log.warning("seed: manifest unreadable (%s) — skipping", exc)
        return 0

    media = settings.media_dir / "creatures"
    media.mkdir(parents=True, exist_ok=True)

    # An empty table plus a media dir that ALREADY HAS ART is not a first run —
    # it is a database pointed somewhere unexpected. Seeding here would copy the
    # starter heroes over files named {id}.webp that belong to a real player's
    # creatures, which is exactly what happened on 2026-08-09 (recovered via
    # scripts/recover_heroes.py). Art on disk wins over an empty table, always.
    existing_art = next(media.iterdir(), None)
    if existing_art is not None:
        log.warning(
            "seed: creatures table is empty but %s already holds art (e.g. %s) "
            "— refusing to seed. This database is almost certainly not the one "
            "that media belongs to; check DATABASE_URL and CHIMERA_MEDIA_DIR.",
            media, existing_art.name,
        )
        return 0

    created = 0
    for key in keys:
        entry = seed_dir / key
        record_path = entry / "record.json"
        hero_src = _art(entry, "hero")
        thumb_src = _art(entry, "thumb")
        if not (record_path.exists() and hero_src and thumb_src):
            log.warning("seed: %s is incomplete — skipping this entry", entry)
            continue
        try:
            payload = json.loads(record_path.read_text())
            record = CreatureRecord.model_validate(payload["record"])
            sources = list(payload.get("sources") or [])
        except Exception as exc:  # noqa: BLE001 - one bad entry must not block boot
            log.warning("seed: %s record invalid (%s) — skipping this entry", key, exc)
            continue

        creature = Creature(
            sources=sources,
            record_status=RecordStatus.complete,
            image_status=ImageStatus.complete,
            favorite=False, wins=0, losses=0, championships=0, records={},
            **_record_fields(record),
        )
        session.add(creature)
        await session.flush()  # assign the id the media filenames are keyed on

        # The extension follows the pack: WebP once converted, PNG for an older
        # pack. The runtime reads whatever the stored path says, so both work.
        shutil.copyfile(hero_src, media / f"{creature.id}{hero_src.suffix}")
        shutil.copyfile(thumb_src, media / f"{creature.id}_thumb{thumb_src.suffix}")
        creature.hero_image_path = f"/media/creatures/{creature.id}{hero_src.suffix}"
        creature.thumb_path = f"/media/creatures/{creature.id}_thumb{thumb_src.suffix}"
        created += 1
        log.info("seed: %s -> creature %d %r (%s)", key, creature.id, record.name, record.rarity)

    await session.commit()
    log.info("seed: starter crew ready — %d creatures", created)
    return created
