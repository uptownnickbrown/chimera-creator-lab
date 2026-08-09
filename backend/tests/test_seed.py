"""Boot seeding of the committed starter crew (services/seed.py)."""
from __future__ import annotations

import io
import json

import pytest
from conftest import SOURCE_SETS

SEED_KEYS = [f"crew_{i}" for i in range(8)]


def _webp_bytes(size: int = 64) -> bytes:
    """A tiny valid RGBA WebP with transparent corners (stand-in for hero art)."""
    from PIL import Image

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for x in range(8, size - 8):
        for y in range(8, size - 8):
            img.putpixel((x, y), (40, 200, 255, 255))
    out = io.BytesIO()
    img.save(out, "WEBP")
    return out.getvalue()


def _build_seed_pack(data_dir, keys=SEED_KEYS) -> None:
    """A complete data/seed pack built from the deterministic stub generator."""
    from app.services.generation import build_stub_record

    seed_dir = data_dir / "seed"
    art = _webp_bytes()
    for i, key in enumerate(keys):
        sources = SOURCE_SETS[i % len(SOURCE_SETS)]
        record = build_stub_record(sources, nonce=key)
        entry = seed_dir / key
        entry.mkdir(parents=True)
        (entry / "record.json").write_text(json.dumps(
            {"key": key, "sources": sources, "record": record.model_dump()}
        ))
        (entry / "hero.webp").write_bytes(art)
        (entry / "thumb.webp").write_bytes(art)
    (seed_dir / "manifest.json").write_text(json.dumps({"keys": list(keys)}))


@pytest.fixture
async def seed_env(tmp_path, monkeypatch):
    """Isolated settings/engine like conftest.client, without the HTTP layer."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("CHIMERA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CHIMERA_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("CHIMERA_STUB_AI", "1")

    from app import config
    from app import db as dbmod

    config.get_settings.cache_clear()
    dbmod._engine = None
    dbmod._session_factory = None
    await dbmod.create_all()

    yield tmp_path

    await dbmod.engine().dispose()
    dbmod._engine = None
    dbmod._session_factory = None
    config.get_settings.cache_clear()


async def test_seeds_empty_db_with_full_crew(seed_env):
    from sqlalchemy import select

    from app.db import session_factory
    from app.models import Creature
    from app.services.seed import seed_if_empty

    _build_seed_pack(seed_env / "data")

    async with session_factory()() as db:
        assert await seed_if_empty(db) == 8

    async with session_factory()() as db:
        rows = list((await db.execute(select(Creature))).scalars())
    assert len(rows) == 8
    media = seed_env / "media" / "creatures"
    for c in rows:
        assert c.record_status.value == "complete"
        assert c.image_status.value == "complete"
        assert c.name and c.rarity in {"Uncommon", "Rare", "Epic", "Legendary"}
        assert len(c.sources) == 4
        assert (c.wins, c.losses, c.championships, c.favorite) == (0, 0, 0, False)
        assert c.created_at is not None
        assert c.hero_image_path == f"/media/creatures/{c.id}.webp"
        assert c.thumb_path == f"/media/creatures/{c.id}_thumb.webp"
        assert (media / f"{c.id}.webp").exists()
        assert (media / f"{c.id}_thumb.webp").exists()

    # Second boot: the crew is already there — a strict no-op.
    async with session_factory()() as db:
        assert await seed_if_empty(db) == 0
    async with session_factory()() as db:
        rows = list((await db.execute(select(Creature))).scalars())
    assert len(rows) == 8


async def test_any_existing_creature_means_no_op(seed_env):
    from sqlalchemy import select

    from app.db import session_factory
    from app.models import Creature, ImageStatus, RecordStatus
    from app.services.seed import seed_if_empty

    _build_seed_pack(seed_env / "data")

    # Even a single FAILED creature counts as player history.
    async with session_factory()() as db:
        db.add(Creature(name="Wreck", sources=[], record_status=RecordStatus.failed,
                        image_status=ImageStatus.failed))
        await db.commit()

    async with session_factory()() as db:
        assert await seed_if_empty(db) == 0
    async with session_factory()() as db:
        rows = list((await db.execute(select(Creature))).scalars())
    assert [c.name for c in rows] == ["Wreck"]


async def test_existing_art_blocks_seeding_an_empty_table(seed_env):
    """The 2026-08-09 data loss, pinned.

    A server booted against the WRONG (empty) database while sharing the real
    player's media dir. The table looked like a first run, so the seeder copied
    its starter heroes over media/creatures/{id} art — destroying seven of
    Henry's creature renders. Art already on disk now vetoes seeding.
    """
    from sqlalchemy import select

    from app.db import session_factory
    from app.models import Creature
    from app.services.seed import seed_if_empty

    _build_seed_pack(seed_env / "data")

    media = seed_env / "media" / "creatures"
    media.mkdir(parents=True, exist_ok=True)
    precious = media / "1.webp"
    precious.write_bytes(b"RIFF----WEBP-henrys-creature")

    async with session_factory()() as db:
        assert await seed_if_empty(db) == 0
    async with session_factory()() as db:
        assert list((await db.execute(select(Creature))).scalars()) == []
    assert precious.read_bytes() == b"RIFF----WEBP-henrys-creature"


async def test_missing_manifest_is_a_quiet_no_op(seed_env):
    from sqlalchemy import select

    from app.db import session_factory
    from app.models import Creature
    from app.services.seed import seed_if_empty

    # No data/seed at all — seeding logs and continues.
    async with session_factory()() as db:
        assert await seed_if_empty(db) == 0
    async with session_factory()() as db:
        assert list((await db.execute(select(Creature))).scalars()) == []
