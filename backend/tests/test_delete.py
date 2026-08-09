"""Deletability (playtest rule: anything creatable is deletable) + ghost history.

Covers DELETE /api/creatures/{id}, DELETE /api/library/custom/{slug}, and
DELETE /api/tournaments/{id} — including the paths where deleted things are
still referenced by history (tournaments, battles, fused creatures).
"""
from __future__ import annotations

from conftest import make_creature, make_roster
from test_summon import author_library


def _media_dir():
    from app.config import get_settings

    d = get_settings().media_dir / "creatures"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _run_to_completion(client, tid: int) -> dict:
    """Resolve every match by following next_match_id (dogfoods the field)."""
    while True:
        t = (await client.get(f"/api/tournaments/{tid}")).json()
        if t["next_match_id"] is None:
            return t
        resolved = await client.post(
            f"/api/tournaments/{tid}/matches/{t['next_match_id']}/resolve"
        )
        assert resolved.status_code == 200, resolved.text


async def _battle_count() -> int:
    from sqlalchemy import func, select

    from app.db import session_factory
    from app.models import Battle

    async with session_factory()() as db:
        return (await db.execute(select(func.count()).select_from(Battle))).scalar_one()


# -- creatures ------------------------------------------------------------------

async def test_delete_creature_removes_row_and_media(client):
    creature = await make_creature(client, 0)
    cid = creature["id"]
    hero = _media_dir() / f"{cid}.png"
    thumb = _media_dir() / f"{cid}_thumb.png"
    hero.write_bytes(b"png")
    thumb.write_bytes(b"png")

    deleted = await client.delete(f"/api/creatures/{cid}")
    assert deleted.status_code == 200
    assert deleted.json() == {"creature_id": cid, "deleted": True}

    assert (await client.get(f"/api/creatures/{cid}")).status_code == 404
    assert not hero.exists() and not thumb.exists()
    assert (await client.delete(f"/api/creatures/{cid}")).status_code == 404


async def test_delete_creature_in_any_state(client):
    """Failed/half-generated rows are deletable too — no state gate."""
    from app.db import session_factory
    from app.models import Creature, ImageStatus, RecordStatus

    async with session_factory()() as db:
        wreck = Creature(name="", sources=[], record_status=RecordStatus.failed,
                         image_status=ImageStatus.failed)
        db.add(wreck)
        await db.commit()
        wreck_id = wreck.id

    assert (await client.delete(f"/api/creatures/{wreck_id}")).status_code == 200
    assert (await client.get(f"/api/creatures/{wreck_id}")).status_code == 404


async def test_delete_creature_keeps_completed_tournament_history(client):
    roster = await make_roster(client, 8)
    t = await client.post("/api/tournaments",
                          json={"entrant_ids": [c["id"] for c in roster]})
    tid = t.json()["id"]
    final = await _run_to_completion(client, tid)
    assert final["status"] == "complete"
    battles_before = await _battle_count()
    champion_id = final["champion_id"]

    # Delete the champion AND one other entrant: history must render as ghosts.
    other = next(i for i in final["entrant_ids"] if i != champion_id)
    for cid in (champion_id, other):
        assert (await client.delete(f"/api/creatures/{cid}")).status_code == 200

    replayed = (await client.get(f"/api/tournaments/{tid}")).json()
    assert replayed["status"] == "complete"
    assert replayed["champion_id"] == champion_id  # id survives as a ghost
    assert replayed["entrant_ids"] == final["entrant_ids"]
    assert len(replayed["entrants"]) == 6  # deleted entrants drop from summaries only
    assert replayed["rounds"] == final["rounds"]

    # Replaying an already-resolved match still serves the cached battle.
    replay = await client.post(f"/api/tournaments/{tid}/matches/r0m0/resolve")
    assert replay.status_code == 200
    assert replay.json()["battle"]["cached"] is True

    # The determinism cache is untouched — never cascade-deleted.
    assert await _battle_count() == battles_before

    # History listing and hall/profile views survive the ghosts.
    assert (await client.get("/api/tournaments")).status_code == 200
    assert (await client.get("/api/hall")).status_code == 200
    assert (await client.get("/api/profile")).status_code == 200


async def test_delete_fighter_in_active_tournament_degrades_to_400(client):
    roster = await make_roster(client, 8)
    t = (await client.post("/api/tournaments",
                           json={"entrant_ids": [c["id"] for c in roster]})).json()
    victim = t["rounds"][0]["matches"][0]["a"]
    assert (await client.delete(f"/api/creatures/{victim}")).status_code == 200

    unresolvable = await client.post(f"/api/tournaments/{t['id']}/matches/r0m0/resolve")
    assert unresolvable.status_code == 400  # graceful, never a 500
    assert (await client.get(f"/api/tournaments/{t['id']}")).status_code == 200


# -- custom parts ----------------------------------------------------------------

async def test_delete_custom_part_row_registry_and_portrait(client, tmp_path):
    author_library(tmp_path)
    conjured = (await client.post("/api/library/summon",
                                  json={"query": "axolotl dragon"})).json()
    assert conjured["status"] == "conjured"
    slug = conjured["source"]["slug"]  # custom/axolotl-dragon

    from app.config import get_settings

    portrait = get_settings().media_dir / "parts" / "custom_axolotl-dragon.png"
    portrait.parent.mkdir(parents=True, exist_ok=True)
    portrait.write_bytes(b"png")

    deleted = await client.delete("/api/library/custom/axolotl-dragon")
    assert deleted.status_code == 200
    assert deleted.json() == {"slug": slug, "deleted": True}
    assert not portrait.exists()

    # Gone from the merged picker library and from the DB.
    slugs = {s["slug"] for s in (await client.get("/api/library")).json()["sources"]}
    assert slug not in slugs
    from sqlalchemy import select

    from app.db import session_factory
    from app.models import CustomPart

    async with session_factory()() as db:
        row = (await db.execute(
            select(CustomPart).where(CustomPart.slug == slug))).scalar_one_or_none()
    assert row is None

    assert (await client.delete("/api/library/custom/axolotl-dragon")).status_code == 404


async def test_delete_custom_part_accepts_full_slug_form(client, tmp_path):
    author_library(tmp_path)
    await client.post("/api/library/summon", json={"query": "quokka"})
    deleted = await client.delete("/api/library/custom/custom/quokka")
    assert deleted.status_code == 200
    assert deleted.json()["slug"] == "custom/quokka"


async def test_curated_parts_are_never_deletable(client, tmp_path):
    author_library(tmp_path)
    forbidden = await client.delete("/api/library/custom/dragon")
    assert forbidden.status_code == 403
    assert "curated" in forbidden.json()["detail"]
    # Still in the library, of course.
    slugs = {s["slug"] for s in (await client.get("/api/library")).json()["sources"]}
    assert "dragon" in slugs

    assert (await client.delete("/api/library/custom/no-such-part")).status_code == 404


async def test_creatures_fused_from_deleted_part_keep_working(client, tmp_path):
    author_library(tmp_path)
    await client.post("/api/library/summon", json={"query": "axolotl dragon"})
    created = await client.post("/api/creatures", json={
        "source_slugs": ["custom/axolotl-dragon", "dragon", "shark", "cobra"]})
    assert created.status_code == 200
    cid = created.json()["creature_id"]

    assert (await client.delete("/api/library/custom/axolotl-dragon")).status_code == 200

    # Summary, detail, and prompt-brief paths must not assume the slug resolves.
    detail = (await client.get(f"/api/creatures/{cid}")).json()
    assert "custom/axolotl-dragon" in detail["sources"]
    assert (await client.get("/api/creatures")).status_code == 200

    from app.services.generation import _source_briefs

    briefs = _source_briefs(detail["sources"])  # must not raise
    assert "Axolotl Dragon" in briefs  # title-cased ghost name fallback

    # But NEW fusions can no longer use the deleted part.
    rejected = await client.post("/api/creatures", json={
        "source_slugs": ["custom/axolotl-dragon", "dragon", "shark", "cobra"]})
    assert rejected.status_code == 400


# -- tournaments -----------------------------------------------------------------

async def test_delete_tournament_any_status_keeps_battle_cache(client):
    roster = await make_roster(client, 8)
    ids = [c["id"] for c in roster]

    # Abandon an in-flight tournament mid-round.
    t1 = (await client.post("/api/tournaments", json={"entrant_ids": ids})).json()
    await client.post(f"/api/tournaments/{t1['id']}/matches/r0m0/resolve")
    battles_before = await _battle_count()
    assert battles_before == 1

    deleted = await client.delete(f"/api/tournaments/{t1['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"tournament_id": t1["id"], "deleted": True}
    assert (await client.get(f"/api/tournaments/{t1['id']}")).status_code == 404
    assert await _battle_count() == battles_before  # cache untouched

    # Remove a completed history entry too.
    t2 = (await client.post("/api/tournaments", json={"entrant_ids": ids})).json()
    await _run_to_completion(client, t2["id"])
    assert (await client.delete(f"/api/tournaments/{t2['id']}")).status_code == 200
    assert (await client.get("/api/tournaments")).json() == []
    assert (await client.delete(f"/api/tournaments/{t2['id']}")).status_code == 404
