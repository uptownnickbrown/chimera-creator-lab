"""Summon New Creature: local alias resolution, ambiguity, conjure, redirect.

No network anywhere — CHIMERA_STUB_AI=1 (conftest) keeps the resolver on its
deterministic stub, and the AI-decision paths monkeypatch summon.resolve just
like the rest of the suite stubs its AI calls.
"""
from __future__ import annotations

import json

from app.schemas import SummonResolution

# A miniature authored library exercising exactly the shapes that matter:
# aliases, misspellings, and a deliberate ambiguity pair ("sea monster").
MINI_LIBRARY = [
    {"slug": "dragon", "name": "Dragon", "category": "mythic",
     "kid_blurb": "Breathes fire!", "contributes": ["fire breath", "huge wings"],
     "aliases": ["draggon", "wyvern", "fire dragon"]},
    {"slug": "sabertooth", "name": "Sabertooth Tiger", "category": "extinct",
     "kid_blurb": "Ice-age super cat!", "contributes": ["giant fangs"],
     "aliases": ["saber tooth", "sabertooth tiger", "smilodon"]},
    {"slug": "kraken", "name": "Kraken", "category": "mythic",
     "kid_blurb": "Tentacles!", "contributes": ["grabbing tentacles"],
     "aliases": ["giant squid", "sea monster"]},
    {"slug": "leviathan", "name": "Leviathan", "category": "mythic",
     "kid_blurb": "Huge!", "contributes": ["ocean power"],
     "aliases": ["sea monster"]},
    {"slug": "shark", "name": "Great White Shark", "category": "living",
     "kid_blurb": "Chomp!", "contributes": ["powerful bite"], "aliases": ["gws"]},
    {"slug": "cobra", "name": "Cobra", "category": "living",
     "kid_blurb": "Sss!", "contributes": ["venom strike"], "aliases": []},
]


def author_library(tmp_path):
    data_dir = tmp_path / "data"  # conftest points CHIMERA_DATA_DIR here
    data_dir.mkdir(exist_ok=True)
    (data_dir / "source_creatures.json").write_text(json.dumps(MINI_LIBRARY))

    from app.services import library as lib

    lib.load_library()


async def test_library_serves_aliases(client, tmp_path):
    author_library(tmp_path)
    body = (await client.get("/api/library")).json()
    assert body["loaded"] is True
    dragon = next(s for s in body["sources"] if s["slug"] == "dragon")
    assert dragon["aliases"] == ["draggon", "wyvern", "fire dragon"]
    assert dragon["custom"] is False


async def test_summon_matches_local_alias_without_ai(client, tmp_path, monkeypatch):
    author_library(tmp_path)

    async def explode(query):  # a local hit must never reach the resolver
        raise AssertionError("resolver called for a local match")

    from app.services import summon as summon_svc

    monkeypatch.setattr(summon_svc, "resolve", explode)

    for query in ("Draggon!", "  wyvern ", "SABER-TOOTH", "sharks"):
        res = await client.post("/api/library/summon", json={"query": query})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "matched", query
        assert body["source"]["slug"] in {"dragon", "sabertooth", "shark"}


async def test_summon_ambiguity_disambiguates(client, tmp_path):
    author_library(tmp_path)
    body = (await client.post("/api/library/summon", json={"query": "Sea Monster"})).json()
    assert body["status"] == "disambiguate"
    assert {c["slug"] for c in body["candidates"]} == {"kraken", "leviathan"}


async def test_summon_conjures_persists_and_merges(client, tmp_path):
    author_library(tmp_path)
    res = await client.post("/api/library/summon", json={"query": "axolotl dragon"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "conjured"
    source = body["source"]
    assert source["slug"] == "custom/axolotl-dragon"
    assert source["custom"] is True
    assert source["category"] in {"mythic", "extinct", "living"}
    assert len(source["traits"]) == 3
    assert source["contribution"].startswith("Adds")
    assert body["portrait_status"] in {"rendering", "failed"}  # stub mode: no render

    # Merged into the library picker payload.
    lib = (await client.get("/api/library")).json()
    merged = next(s for s in lib["sources"] if s["slug"] == "custom/axolotl-dragon")
    assert merged["custom"] is True

    # Summoning it again is a match, never a duplicate.
    again = (await client.post("/api/library/summon", json={"query": "Axolotl Dragon"})).json()
    assert again["status"] == "matched"
    assert again["source"]["slug"] == "custom/axolotl-dragon"

    # First-class fusion source immediately, portrait still pending.
    created = await client.post("/api/creatures", json={
        "source_slugs": ["custom/axolotl-dragon", "dragon", "shark", "cobra"]})
    assert created.status_code == 200, created.text
    record = (await client.get(f"/api/creatures/{created.json()['creature_id']}")).json()
    assert "custom/axolotl-dragon" in record["sources"]


async def test_summon_redirect_is_kind_and_persists_nothing(client, tmp_path, monkeypatch):
    author_library(tmp_path)

    async def fake_resolve(query):
        return SummonResolution(
            decision="redirect", library_slugs=[], name="", category="living",
            blurb="", traits=[], contribution="", portrait_description="",
            redirect_message="The summoning circle only answers to creatures — "
                             "try a dinosaur or a deep-sea beast!",
        )

    from app.services import summon as summon_svc

    monkeypatch.setattr(summon_svc, "resolve", fake_resolve)

    body = (await client.post("/api/library/summon", json={"query": "homework"})).json()
    assert body["status"] == "redirect"
    assert "creatures" in body["message"]
    assert body["source"] is None
    slugs = {s["slug"] for s in (await client.get("/api/library")).json()["sources"]}
    assert not any(s.startswith("custom/") for s in slugs)


async def test_summon_resolver_misspelling_maps_to_library(client, tmp_path, monkeypatch):
    author_library(tmp_path)

    async def fake_resolve(query):
        assert query == "grate wite shark"
        return SummonResolution(
            decision="library", library_slugs=["shark"], name="", category="living",
            blurb="", traits=[], contribution="", portrait_description="",
            redirect_message="",
        )

    from app.services import summon as summon_svc

    monkeypatch.setattr(summon_svc, "resolve", fake_resolve)

    body = (await client.post("/api/library/summon",
                              json={"query": "grate wite shark"})).json()
    assert body["status"] == "matched"
    assert body["source"]["slug"] == "shark"


async def test_summon_resolver_ambiguity_maps_to_disambiguate(client, tmp_path, monkeypatch):
    author_library(tmp_path)

    async def fake_resolve(query):
        return SummonResolution(
            decision="library", library_slugs=["kraken", "leviathan", "ghost-slug"],
            name="", category="living", blurb="", traits=[], contribution="",
            portrait_description="", redirect_message="",
        )

    from app.services import summon as summon_svc

    monkeypatch.setattr(summon_svc, "resolve", fake_resolve)

    body = (await client.post("/api/library/summon", json={"query": "ocean titan"})).json()
    assert body["status"] == "disambiguate"
    assert {c["slug"] for c in body["candidates"]} == {"kraken", "leviathan"}


async def test_summoned_parts_survive_reboot(client, tmp_path):
    """load_custom_parts re-merges DB rows after a library reload (boot path)."""
    author_library(tmp_path)
    await client.post("/api/library/summon", json={"query": "quokka"})

    from app import db as dbmod
    from app.services import library as lib
    from app.services import summon as summon_svc

    lib.load_library()  # simulates restart: registry resets, DB persists
    assert lib.source_by_slug("custom/quokka") is None
    async with dbmod.session_factory()() as db:
        assert await summon_svc.load_custom_parts(db) == 1
    assert lib.source_by_slug("custom/quokka").custom is True
