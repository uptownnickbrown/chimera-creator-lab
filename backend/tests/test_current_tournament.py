"""Single active tournament (request #7), /current convenience, final_art flow."""
from __future__ import annotations

from conftest import make_roster


async def _create(client, roster) -> dict:
    r = await client.post("/api/tournaments", json={"entrant_ids": [c["id"] for c in roster]})
    assert r.status_code == 200, r.text
    return r.json()


async def _resolve_all(client, tid: int) -> dict:
    while True:
        t = (await client.get(f"/api/tournaments/{tid}")).json()
        if t["next_match_id"] is None:
            return t
        r = await client.post(f"/api/tournaments/{tid}/matches/{t['next_match_id']}/resolve")
        assert r.status_code == 200, r.text


async def test_second_active_tournament_is_409(client):
    roster = await make_roster(client, 8)
    first = await _create(client, roster)

    blocked = await client.post(
        "/api/tournaments", json={"entrant_ids": [c["id"] for c in roster]}
    )
    assert blocked.status_code == 409
    assert str(first["id"]) in blocked.json()["detail"]

    # Abandoning (DELETE) clears the way...
    await client.delete(f"/api/tournaments/{first['id']}")
    second = await _create(client, roster)

    # ...and so does finishing: a COMPLETE tournament never blocks a new one.
    await _resolve_all(client, second["id"])
    third = await _create(client, roster)
    assert third["status"] == "active"

    # Completed tournaments stay listable as revisitable history (request #12).
    listed = (await client.get("/api/tournaments")).json()
    assert {t["id"] for t in listed} == {second["id"], third["id"]}
    assert next(t for t in listed if t["id"] == second["id"])["status"] == "complete"


async def test_current_returns_active_tournament_with_next_match(client):
    # No tournament at all -> JSON null, not 404.
    empty = await client.get("/api/tournaments/current")
    assert empty.status_code == 200
    assert empty.json() is None

    roster = await make_roster(client, 8)
    t = await _create(client, roster)

    current = (await client.get("/api/tournaments/current")).json()
    assert current["id"] == t["id"]
    assert current["status"] == "active"
    assert current["next_match_id"] == "r0m0"
    assert current["final_art"] is None

    # next_match_id walks the bracket in play order as matches resolve.
    await client.post(f"/api/tournaments/{t['id']}/matches/r0m0/resolve")
    assert (await client.get("/api/tournaments/current")).json()["next_match_id"] == "r0m1"
    for match_id in ("r0m1", "r0m2", "r0m3"):
        await client.post(f"/api/tournaments/{t['id']}/matches/{match_id}/resolve")
    assert (await client.get("/api/tournaments/current")).json()["next_match_id"] == "r1m0"

    # Completing the bracket empties /current; the view's pointer goes null.
    final = await _resolve_all(client, t["id"])
    assert final["status"] == "complete"
    assert final["next_match_id"] is None
    assert (await client.get("/api/tournaments/current")).json() is None


async def test_final_art_lands_in_tournament_view(client, monkeypatch):
    """final_art is a typed TournamentView field fed from the bracket JSON;
    once _final_art_task commits a path it appears in every response."""
    roster = await make_roster(client, 8)
    t = await _create(client, roster)
    tid = t["id"]

    # Semifinals done -> finalists known (stub mode skips the auto-kickoff,
    # so drive the task directly with a stubbed render).
    for match_id in ("r0m0", "r0m1", "r0m2", "r0m3", "r1m0", "r1m1"):
        await client.post(f"/api/tournaments/{tid}/matches/{match_id}/resolve")
    view = (await client.get(f"/api/tournaments/{tid}")).json()
    final_match = view["rounds"][2]["matches"][0]
    a, b = final_match["a"], final_match["b"]
    assert a and b and view["final_art"] is None

    stub_path = f"/media/creatures/final_{min(a, b)}_{max(a, b)}.webp"

    async def fake_render(fa, fb):
        assert {fa.id, fb.id} == {a, b}
        return stub_path

    from app.api import tournaments as tournaments_api

    monkeypatch.setattr(tournaments_api.images, "generate_championship_art", fake_render)
    await tournaments_api._final_art_task(tid, a, b)

    view = (await client.get(f"/api/tournaments/{tid}")).json()
    assert view["final_art"] == stub_path
    current = (await client.get("/api/tournaments/current")).json()
    assert current["final_art"] == stub_path  # /current carries it too
