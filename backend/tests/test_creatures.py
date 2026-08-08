"""Creation, the reveal poll, codex sorts, favorite and name reroll."""
from __future__ import annotations

from conftest import SOURCE_SETS, make_creature, make_roster


async def test_create_then_get_flow(client):
    created = await client.post("/api/creatures", json={"source_slugs": SOURCE_SETS[0]})
    assert created.status_code == 200
    payload = created.json()
    assert payload["creature_id"] > 0
    assert payload["status"] in {"pending", "complete", "failed"}

    # The reveal screen polls this endpoint until image_status settles.
    got = await client.get(f"/api/creatures/{payload['creature_id']}")
    assert got.status_code == 200
    record = got.json()

    assert record["sources"] == SOURCE_SETS[0]
    assert record["name"] and record["title"]
    assert record["rarity"] in {"Uncommon", "Rare", "Epic", "Legendary"}
    assert 3 <= len(record["abilities"]) <= 4
    assert all(len(a["sources"]) == 2 for a in record["abilities"])  # synergy rule
    assert 2 <= len(record["strengths"]) <= 3
    assert 2 <= len(record["weaknesses"]) <= 3
    assert set(record["core_stats"]) == {
        "power", "speed", "armor", "size", "special_name", "special"
    }
    assert all(0 <= record["core_stats"][k] <= 100
               for k in ("power", "speed", "armor", "size", "special"))
    assert len(record["environment_affinities"]) == 9
    assert "sim_profile" not in record  # hidden stats never reach the child-facing API
    assert record["image_status"] in {"pending", "complete", "failed"}


async def test_generation_is_deterministic_in_the_sources(client):
    first = await make_creature(client, 0)
    second = await make_creature(client, 0)
    assert first["id"] != second["id"]
    assert first["name"] == second["name"]
    assert first["core_stats"] == second["core_stats"]


async def test_create_rejects_bad_input(client):
    too_few = await client.post("/api/creatures", json={"source_slugs": ["dragon", "shark"]})
    assert too_few.status_code == 422

    dupes = await client.post(
        "/api/creatures", json={"source_slugs": ["dragon", "dragon", "shark", "cobra"]}
    )
    assert dupes.status_code == 400


async def test_missing_creature_is_404(client):
    assert (await client.get("/api/creatures/999")).status_code == 404


async def test_codex_sorts(client):
    roster = await make_roster(client, 5)

    newest = (await client.get("/api/creatures?sort=newest")).json()
    assert [c["id"] for c in newest] == sorted((c["id"] for c in roster), reverse=True)

    for sort, stat in (("biggest", "size"), ("fastest", "speed"), ("strongest", "power")):
        rows = (await client.get(f"/api/creatures?sort={sort}")).json()
        values = [r["core_stats"][stat] for r in rows]
        assert values == sorted(values, reverse=True), sort

    assert (await client.get("/api/creatures?sort=favorites")).json() == []
    assert (await client.get("/api/creatures?sort=nonsense")).status_code == 422


async def test_favorite_toggles_and_filters(client):
    creature = await make_creature(client, 0)

    on = await client.post(f"/api/creatures/{creature['id']}/favorite")
    assert on.json() == {"creature_id": creature["id"], "favorite": True}
    favorites = (await client.get("/api/creatures?sort=favorites")).json()
    assert [c["id"] for c in favorites] == [creature["id"]]

    off = await client.post(f"/api/creatures/{creature['id']}/favorite")
    assert off.json()["favorite"] is False
    assert (await client.get("/api/creatures?sort=favorites")).json() == []


async def test_rename_rerolls_and_persists(client):
    creature = await make_creature(client, 1)

    renamed = await client.post(f"/api/creatures/{creature['id']}/rename")
    assert renamed.status_code == 200
    new_name = renamed.json()["name"]
    assert new_name and new_name != creature["name"]

    reloaded = (await client.get(f"/api/creatures/{creature['id']}")).json()
    assert reloaded["name"] == new_name
    assert reloaded["core_stats"] == creature["core_stats"]  # only the name changes


async def test_library_tolerates_missing_data_files(client):
    body = (await client.get("/api/library")).json()
    assert body["loaded"] is False
    assert body["sources"] == []
    # Environments always resolve — the nine schema slugs are the fallback.
    assert len(body["environments"]) == 9


async def test_profile_and_empty_hall(client):
    profile = (await client.get("/api/profile")).json()
    assert profile["name"] == "Henry"
    assert profile["total_creatures"] == 0

    await make_roster(client, 3)
    profile = (await client.get("/api/profile")).json()
    assert profile["total_creatures"] == 3
    assert profile["xp"] > 0
    assert profile["biggest_creature"] is not None

    hall = (await client.get("/api/hall")).json()
    assert hall["champions"] == []
    assert hall["top_winners"] == []
    assert {r["key"] for r in hall["records"]} == {"biggest", "fastest", "strongest"}
