"""Boot-time orphan sweep: nothing may be left polling a ghost.

Generation tasks live in the process, so a restart (or a crash) strands every
row that was mid-flight. The sweep runs at boot and turns each stranded row
into a state the UI has a button for.
"""
from __future__ import annotations


async def test_sweep_clears_everything_a_dead_process_stranded(client):
    from app.db import session_factory
    from app.main import _sweep_orphans
    from app.models import (
        Creature,
        CustomPart,
        ImageStatus,
        RecordStatus,
        Tournament,
    )

    async with session_factory()() as db:
        db.add_all([
            Creature(name="Half-written", record_status=RecordStatus.generating,
                     image_status=ImageStatus.pending),
            Creature(name="Text done, art stranded",
                     record_status=RecordStatus.complete,
                     image_status=ImageStatus.pending),
            CustomPart(slug="custom/ghost_wing", name="Ghost Wing",
                       portrait_status=ImageStatus.pending),
            # The Finale overlay polls final_art forever while it says "pending".
            Tournament(name="Stranded finale", entrant_ids=[],
                       bracket={"rounds": [], "final_art": "pending"}),
            Tournament(name="Real key art", entrant_ids=[],
                       bracket={"rounds": [], "final_art": "/media/final.png"}),
        ])
        await db.commit()

    await _sweep_orphans()

    async with session_factory()() as db:
        from sqlalchemy import select

        creatures = (await db.execute(select(Creature))).scalars().all()
        by_name = {c.name: c for c in creatures}
        assert by_name["Half-written"].record_status is RecordStatus.failed
        assert by_name["Half-written"].image_status is ImageStatus.failed
        assert by_name["Text done, art stranded"].record_status is RecordStatus.complete
        assert by_name["Text done, art stranded"].image_status is ImageStatus.failed

        part = (await db.execute(select(CustomPart))).scalars().one()
        assert part.portrait_status is ImageStatus.failed

        arts = {t.name: t.bracket.get("final_art")
                for t in (await db.execute(select(Tournament))).scalars()}
        assert arts["Stranded finale"] is None
        # A finished render is not an orphan — the sweep must leave it alone.
        assert arts["Real key art"] == "/media/final.png"


async def test_sweep_is_idempotent_on_a_clean_database(client):
    from app.main import _sweep_orphans

    await _sweep_orphans()
    await _sweep_orphans()
