"""Bracket mode: predict -> simulate -> explain -> advance -> crown (spec §7, §15)."""
from __future__ import annotations

import asyncio
import copy
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Battle, Creature, Tournament, TournamentStatus
from ..schemas import (
    BattleReason,
    BattleView,
    CreateTournamentRequest,
    HealthRemaining,
    PredictRequest,
    ResolveResponse,
    TournamentView,
)
from ..services import ai, images
from ..services import battle as battle_svc
from ..services import tournament as bracket_svc
from .common import XP_CORRECT_PREDICTION, award_xp, get_profile, summary

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


# -- helpers ------------------------------------------------------------------

async def _load(db: AsyncSession, tournament_id: int) -> Tournament:
    row = await db.get(Tournament, tournament_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No tournament {tournament_id}")
    return row


async def _view(db: AsyncSession, t: Tournament) -> TournamentView:
    rows = list((await db.execute(
        select(Creature).where(Creature.id.in_(t.entrant_ids or []))
    )).scalars())
    by_id = {c.id: c for c in rows}
    entrants = [summary(by_id[i]) for i in (t.entrant_ids or []) if i in by_id]
    return TournamentView(
        id=t.id,
        name=t.name,
        status=t.status.value if hasattr(t.status, "value") else t.status,
        entrant_ids=t.entrant_ids or [],
        rounds=(t.bracket or {}).get("rounds", []),
        champion_id=t.champion_id,
        entrants=entrants,
        created_at=t.created_at,
        completed_at=t.completed_at,
    )


def _battle_view(b: Battle, match: dict, cached: bool) -> BattleView:
    return BattleView(
        battle_id=b.id,
        match_id=match["id"],
        creature_a_id=b.creature_a_id,
        creature_b_id=b.creature_b_id,
        environment=b.environment,
        winner_id=b.winner_id,
        confidence=b.confidence,
        reasons=[BattleReason(**r) for r in (b.reasons or [])],
        narrative=b.narrative,
        beats=b.beats or [],
        health_remaining=HealthRemaining(**(b.health_remaining or {"a": 0, "b": 0})),
        predicted=match.get("predicted"),
        prediction_correct=match.get("prediction_correct"),
        cached=cached,
    )


def _mutable_bracket(t: Tournament) -> dict:
    """JSON columns need a NEW object to be seen as dirty — never edit in place."""
    return copy.deepcopy(t.bracket or {})


# -- endpoints ----------------------------------------------------------------

@router.post("", response_model=TournamentView)
async def create_tournament(
    body: CreateTournamentRequest, db: AsyncSession = Depends(get_db)
) -> TournamentView:
    if len(set(body.entrant_ids)) != bracket_svc.ENTRANT_COUNT:
        raise HTTPException(status_code=400, detail="Need 8 different creatures")

    found = list((await db.execute(
        select(Creature.id).where(Creature.id.in_(body.entrant_ids))
    )).scalars())
    missing = [i for i in body.entrant_ids if i not in set(found)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown creatures: {missing}")

    t = Tournament(
        name=body.name or "Arena Tournament",
        status=TournamentStatus.active,
        entrant_ids=list(body.entrant_ids),
        bracket=bracket_svc.build_bracket(list(body.entrant_ids)),
    )
    db.add(t)
    await db.flush()
    return await _view(db, t)


@router.get("", response_model=list[TournamentView])
async def list_tournaments(db: AsyncSession = Depends(get_db)) -> list[TournamentView]:
    rows = list((await db.execute(
        select(Tournament).order_by(Tournament.id.desc())
    )).scalars())
    return [await _view(db, t) for t in rows]


@router.get("/{tournament_id}", response_model=TournamentView)
async def read_tournament(
    tournament_id: int, db: AsyncSession = Depends(get_db)
) -> TournamentView:
    return await _view(db, await _load(db, tournament_id))


@router.post("/{tournament_id}/matches/{match_id}/predict", response_model=TournamentView)
async def predict(
    tournament_id: int, match_id: str, body: PredictRequest,
    db: AsyncSession = Depends(get_db),
) -> TournamentView:
    """"Who do you think will win?" — locked in before the match resolves (§7)."""
    t = await _load(db, tournament_id)
    bracket = _mutable_bracket(t)
    found = bracket_svc.find_match(bracket, match_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"No match {match_id}")
    _, _, match = found

    if match["winner"] is not None:
        raise HTTPException(status_code=400, detail="That battle is already over")
    if body.pick_id not in (match["a"], match["b"]):
        raise HTTPException(status_code=400, detail="Pick one of the two fighters")

    match["predicted"] = body.pick_id
    t.bracket = bracket
    return await _view(db, t)


@router.post("/{tournament_id}/matches/{match_id}/resolve", response_model=ResolveResponse)
async def resolve(
    tournament_id: int, match_id: str, db: AsyncSession = Depends(get_db)
) -> ResolveResponse:
    """Run the match, advance the bracket, and crown a champion at the end.

    Battles are permanently cached by canonical key, so a matchup that has
    happened before in ANY tournament replays instantly with the same winner.
    """
    t = await _load(db, tournament_id)
    bracket = _mutable_bracket(t)
    found = bracket_svc.find_match(bracket, match_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"No match {match_id}")
    round_index, match_index, match = found

    if match["a"] is None or match["b"] is None:
        raise HTTPException(status_code=400, detail="That match is still waiting on a fighter")

    # Already fought: replay it. Idempotent, so a double-tap cannot double-count.
    if match["winner"] is not None and match["battle_id"] is not None:
        existing = await db.get(Battle, match["battle_id"])
        return ResolveResponse(
            battle=_battle_view(existing, match, cached=True),
            tournament=await _view(db, t),
        )

    a = await db.get(Creature, match["a"])
    b = await db.get(Creature, match["b"])
    if a is None or b is None:
        raise HTTPException(status_code=400, detail="A fighter in this match no longer exists")

    env = match["environment"]
    key = battle_svc.canonical_key(a.id, b.id, env)
    row = (await db.execute(
        select(Battle).where(Battle.canonical_key == key)
    )).scalar_one_or_none()
    cached = row is not None

    if row is None:
        lo, hi = battle_svc.canonical_pair(a, b)
        result = await battle_svc.resolve_battle(a, b, env)
        row = Battle(
            creature_a_id=lo.id,
            creature_b_id=hi.id,
            environment=env,
            winner_id=int(result.winner_slug_or_id),
            reasons=[r.model_dump() for r in result.reasons],
            narrative=result.narrative,
            beats=result.beats,
            health_remaining=result.health_remaining.model_dump(),
            confidence=result.confidence,
            canonical_key=key,
        )
        db.add(row)
        await db.flush()

    winner_id = row.winner_id
    loser = b if winner_id == a.id else a
    winner = a if winner_id == a.id else b

    winner.wins += 1
    loser.losses += 1

    match["winner"] = winner_id
    match["battle_id"] = row.id
    if match["predicted"] is not None:
        match["prediction_correct"] = match["predicted"] == winner_id
        if match["prediction_correct"]:
            award_xp(await get_profile(db), XP_CORRECT_PREDICTION)

    bracket_svc.advance(bracket, round_index, match_index, winner_id)

    # Semifinals just completed -> both finalists known: pre-generate the
    # championship key art now so the ~74s render hides inside the final
    # prediction + battle and the ceremony never waits (AI_CONTRACTS §3).
    final = bracket["rounds"][-1]["matches"][0]
    if (final.get("a") and final.get("b") and final.get("winner") is None
            and not bracket.get("final_art") and ai.ai_enabled()):
        bracket["final_art"] = "pending"
        asyncio.create_task(_final_art_task(t.id, final["a"], final["b"]))

    if bracket_svc.is_complete(bracket):
        t.status = TournamentStatus.complete
        t.champion_id = bracket_svc.champion_id(bracket)
        t.completed_at = datetime.now(UTC)
        champ = winner if winner.id == t.champion_id else await db.get(Creature, t.champion_id)
        if champ is not None:
            champ.championships += 1
            records = dict(champ.records or {})
            records["champion"] = f"{champ.championships}-Time Champion"
            records.setdefault("first_championship", t.name)
            champ.records = records

    t.bracket = bracket
    return ResolveResponse(
        battle=_battle_view(row, match, cached=cached),
        tournament=await _view(db, t),
    )


async def _final_art_task(tournament_id: int, a_id: int, b_id: int) -> None:
    """Background finals key-art render; owns its session (request one closes)."""
    from ..db import session_factory

    async with session_factory()() as db:
        fa = await db.get(Creature, a_id)
        fb = await db.get(Creature, b_id)
        t = await db.get(Tournament, tournament_id)
        if not (fa and fb and t):
            return
        path = await images.generate_championship_art(fa, fb)
        bracket = copy.deepcopy(t.bracket)
        bracket["final_art"] = path  # None -> ceremony uses composited finale
        t.bracket = bracket
        await db.commit()
