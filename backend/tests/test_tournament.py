"""Full 8-creature bracket run, plus the determinism promise (ARCHITECTURE.md)."""
from __future__ import annotations

import pytest
from conftest import make_roster


@pytest.fixture
def one_environment(monkeypatch):
    """Pin every match to one arena so two brackets pose the same question.

    Environments are picked at random per match in real use; fixing them is what
    lets the test compare a matchup across tournaments.
    """
    from app.services import tournament as bracket_svc

    monkeypatch.setattr(bracket_svc.library, "environment_slugs", lambda: ["deep_ocean"])


async def start_tournament(client, roster) -> dict:
    response = await client.post(
        "/api/tournaments", json={"entrant_ids": [c["id"] for c in roster]}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_bracket_shape(client, one_environment):
    roster = await make_roster(client, 8)
    t = await start_tournament(client, roster)

    assert t["status"] == "active"
    assert [r["name"] for r in t["rounds"]] == ["Quarterfinals", "Semifinals", "Championship"]
    assert [len(r["matches"]) for r in t["rounds"]] == [4, 2, 1]
    assert len(t["entrants"]) == 8

    quarters = t["rounds"][0]["matches"]
    assert [m["id"] for m in quarters] == ["r0m0", "r0m1", "r0m2", "r0m3"]
    seeded = [i for m in quarters for i in (m["a"], m["b"])]
    assert seeded == [c["id"] for c in roster]
    for m in t["rounds"][1]["matches"]:  # later rounds start as TBD
        assert m["a"] is None and m["b"] is None
    assert all(m["environment"] for r in t["rounds"] for m in r["matches"])


async def test_needs_eight_distinct_real_creatures(client):
    roster = await make_roster(client, 8)
    ids = [c["id"] for c in roster]

    short = await client.post("/api/tournaments", json={"entrant_ids": ids[:4]})
    assert short.status_code == 422

    dupes = await client.post("/api/tournaments", json={"entrant_ids": ids[:7] + ids[:1]})
    assert dupes.status_code == 400

    ghosts = await client.post("/api/tournaments", json={"entrant_ids": ids[:7] + [9999]})
    assert ghosts.status_code == 400


async def test_full_run_to_champion(client, one_environment):
    roster = await make_roster(client, 8)
    t = await start_tournament(client, roster)
    tid = t["id"]

    correct_predictions = 0
    for round_index in range(3):
        current = (await client.get(f"/api/tournaments/{tid}")).json()
        for match in current["rounds"][round_index]["matches"]:
            assert match["a"] is not None and match["b"] is not None

            predicted = await client.post(
                f"/api/tournaments/{tid}/matches/{match['id']}/predict",
                json={"pick_id": match["a"]},
            )
            assert predicted.status_code == 200

            resolved = await client.post(
                f"/api/tournaments/{tid}/matches/{match['id']}/resolve"
            )
            assert resolved.status_code == 200, resolved.text
            battle = resolved.json()["battle"]

            assert battle["winner_id"] in (match["a"], match["b"])
            assert len(battle["reasons"]) == 3
            assert all(r["icon"].isascii() and r["icon"].isidentifier()
                       for r in battle["reasons"])  # icon slots, never emoji
            assert 4 <= len(battle["beats"]) <= 6
            assert battle["narrative"]
            assert 0.0 <= battle["confidence"] <= 1.0
            health = battle["health_remaining"]
            assert {health["a"], health["b"]} & {0}  # the loser is knocked out
            assert battle["predicted"] == match["a"]
            assert battle["prediction_correct"] == (battle["winner_id"] == match["a"])
            correct_predictions += bool(battle["prediction_correct"])

    final = (await client.get(f"/api/tournaments/{tid}")).json()
    assert final["status"] == "complete"
    assert final["champion_id"] == final["rounds"][2]["matches"][0]["winner"]
    assert final["completed_at"] is not None

    champion = (await client.get(f"/api/creatures/{final['champion_id']}")).json()
    assert champion["championships"] == 1
    assert champion["wins"] == 3
    assert champion["records"]["champion"] == "1-Time Champion"

    # Seven matches, seven results: 8 -> 4 -> 2 -> 1.
    codex = (await client.get("/api/creatures")).json()
    assert sum(c["wins"] for c in codex) == 7
    assert sum(c["losses"] for c in codex) == 7

    hall = (await client.get("/api/hall")).json()
    assert [c["id"] for c in hall["champions"]] == [final["champion_id"]]
    assert hall["top_winners"]
    assert {r["key"] for r in hall["records"]} >= {"most_wins"}

    profile = (await client.get("/api/profile")).json()
    assert profile["current_champion"]["id"] == final["champion_id"]
    assert profile["battles_won"] == 7
    if correct_predictions:
        assert profile["xp"] >= 25 * correct_predictions


async def test_same_matchup_resolves_identically(client, one_environment):
    """The determinism promise: same (A, B, environment) -> same winner, forever."""
    roster = await make_roster(client, 8)

    first = await start_tournament(client, roster)
    second = await start_tournament(client, roster)  # identical seeding and arena
    assert first["id"] != second["id"]

    a = (await client.post(
        f"/api/tournaments/{first['id']}/matches/r0m0/resolve")).json()["battle"]
    b = (await client.post(
        f"/api/tournaments/{second['id']}/matches/r0m0/resolve")).json()["battle"]

    assert a["winner_id"] == b["winner_id"]
    assert a["battle_id"] == b["battle_id"]  # served from the permanent cache
    assert b["cached"] is True
    assert a["reasons"] == b["reasons"]
    assert a["narrative"] == b["narrative"]
    assert a["health_remaining"] == b["health_remaining"]


async def test_resolving_twice_is_idempotent(client, one_environment):
    roster = await make_roster(client, 8)
    t = await start_tournament(client, roster)

    first = (await client.post(
        f"/api/tournaments/{t['id']}/matches/r0m0/resolve")).json()["battle"]
    again = (await client.post(
        f"/api/tournaments/{t['id']}/matches/r0m0/resolve")).json()["battle"]

    assert first["winner_id"] == again["winner_id"]
    assert again["cached"] is True

    winner = (await client.get(f"/api/creatures/{first['winner_id']}")).json()
    assert winner["wins"] == 1  # replaying a match must not double-count the record


async def test_battle_engine_ignores_call_order(client):
    """A-vs-B and B-vs-A are the same question, so they get the same answer."""
    from app.db import session_factory
    from app.models import Creature
    from app.services import battle as battle_svc

    roster = await make_roster(client, 2)
    async with session_factory()() as db:
        a = await db.get(Creature, roster[0]["id"])
        b = await db.get(Creature, roster[1]["id"])

        forward = await battle_svc.resolve_battle(a, b, "storm_coast")
        backward = await battle_svc.resolve_battle(b, a, "storm_coast")

    assert forward.model_dump() == backward.model_dump()
    assert battle_svc.canonical_key(a.id, b.id, "storm_coast") == \
        battle_svc.canonical_key(b.id, a.id, "storm_coast")


async def test_cannot_resolve_or_predict_out_of_order(client, one_environment):
    roster = await make_roster(client, 8)
    t = await start_tournament(client, roster)
    tid = t["id"]

    early = await client.post(f"/api/tournaments/{tid}/matches/r1m0/resolve")
    assert early.status_code == 400

    bogus = await client.post(f"/api/tournaments/{tid}/matches/r9m9/resolve")
    assert bogus.status_code == 404

    wrong_pick = await client.post(
        f"/api/tournaments/{tid}/matches/r0m0/predict", json={"pick_id": 99999}
    )
    assert wrong_pick.status_code == 400

    await client.post(f"/api/tournaments/{tid}/matches/r0m0/resolve")
    late = await client.post(
        f"/api/tournaments/{tid}/matches/r0m0/predict",
        json={"pick_id": t["rounds"][0]["matches"][0]["a"]},
    )
    assert late.status_code == 400

    assert (await client.get("/api/tournaments/404")).status_code == 404
