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
    DeleteTournamentResponse,
    HealthRemaining,
    PredictRequest,
    ResolveResponse,
    TournamentView,
)
from ..services import ai, images
from ..services import battle as battle_svc
from ..services import tournament as bracket_svc
from . import creatures as creatures_api
from .common import XP_CORRECT_PREDICTION, award_xp, get_profile, summary

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


# -- helpers ------------------------------------------------------------------

async def _load(db: AsyncSession, tournament_id: int) -> Tournament:
    row = await db.get(Tournament, tournament_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No tournament {tournament_id}")
    return row


def _next_match_id(bracket: dict) -> str | None:
    """First unresolved match with both fighters seated, in play order."""
    for rnd in (bracket or {}).get("rounds", []):
        for match in rnd.get("matches", []):
            if (match.get("winner") is None
                    and match.get("a") is not None and match.get("b") is not None):
                return match.get("id")
    return None


async def _view(db: AsyncSession, t: Tournament) -> TournamentView:
    rows = list((await db.execute(
        select(Creature).where(Creature.id.in_(t.entrant_ids or []))
    )).scalars())
    by_id = {c.id: c for c in rows}
    # Deleted entrants simply drop out of `entrants`; their ids stay in
    # entrant_ids and the bracket, where the frontend renders a ghost.
    entrants = [summary(by_id[i]) for i in (t.entrant_ids or []) if i in by_id]
    bracket = t.bracket or {}
    return TournamentView(
        id=t.id,
        name=t.name,
        status=t.status.value if hasattr(t.status, "value") else t.status,
        entrant_ids=t.entrant_ids or [],
        rounds=bracket.get("rounds", []),
        champion_id=t.champion_id,
        entrants=entrants,
        next_match_id=_next_match_id(bracket),
        final_art=bracket.get("final_art"),
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


#: Size gap (core stats are 0-100) that makes a win a giant-slaying.
GIANT_GAP = 25
#: Below this confidence a battle reads as a photo finish — for both sides.
CLOSE_CALL = 0.65


def _battle_records(winner: Creature, loser: Creature, battle: Battle) -> None:
    """Battle-earned records (spec §14/§16 'fun records'): permanent story
    beats derived from data the battle already stores, written into the
    Creature.records JSON the Codex plaques and Hall already render. Keys map
    to painted plaque icons (ui.tsx SLOT_ALIASES). Last telling wins — the
    freshest story is the one worth retelling. Losers earn records too; that
    keeps the whole Codex alive, not just the winners' shelf."""
    w, lo = dict(winner.records or {}), dict(loser.records or {})
    w_size = (winner.core_stats or {}).get("size", 0)
    l_size = (loser.core_stats or {}).get("size", 0)
    if l_size - w_size >= GIANT_GAP:
        w["giant_slayer"] = f"Beat {loser.name or 'a titan'} at size {l_size} vs {w_size}!"
    if battle.confidence < CLOSE_CALL:
        w["closest_call"] = f"Edged out {loser.name or 'a rival'} in a photo finish!"
        lo["toughest"] = f"Pushed {winner.name or 'the winner'} to the very limit!"
    winner.records = w
    loser.records = lo


# The bracket JSON is read-modify-written whole, and three writers can overlap:
# predict, resolve (which holds its copy across a ~15s LLM await), and the
# finals key-art task (~74s render deliberately overlapped with the final
# match). Without serialization the last committer silently reverts the
# others — a lost winner, a lost pick, or paid key art stuck at "pending".
# Single-process app, so one asyncio.Lock per tournament is the whole story;
# every locked section commits before releasing.
_bracket_locks: dict[int, asyncio.Lock] = {}


def _bracket_lock(tournament_id: int) -> asyncio.Lock:
    return _bracket_locks.setdefault(tournament_id, asyncio.Lock())


# -- endpoints ----------------------------------------------------------------

@router.post("", response_model=TournamentView)
async def create_tournament(
    body: CreateTournamentRequest, db: AsyncSession = Depends(get_db)
) -> TournamentView:
    if len(set(body.entrant_ids)) != bracket_svc.ENTRANT_COUNT:
        raise HTTPException(status_code=400, detail="Need 8 different creatures")

    # Single active tournament (request #7): the frontend offers "abandon
    # current?" on 409 and abandons via DELETE /api/tournaments/{id}.
    active = (await db.execute(
        select(Tournament).where(Tournament.status != TournamentStatus.complete).limit(1)
    )).scalar_one_or_none()
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Tournament {active.id} ({active.name!r}) is still in progress — "
            "finish it or abandon it first",
        )

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


@router.get("/current", response_model=TournamentView | None)
async def current_tournament(db: AsyncSession = Depends(get_db)) -> TournamentView | None:
    """The single active (non-complete) tournament, or JSON null.

    `next_match_id` lets the arena drop the player straight into their
    current battle without walking the bracket client-side.
    """
    t = (await db.execute(
        select(Tournament)
        .where(Tournament.status != TournamentStatus.complete)
        .order_by(Tournament.id.desc())
        .limit(1)
    )).scalar_one_or_none()
    return None if t is None else await _view(db, t)


@router.get("/{tournament_id}", response_model=TournamentView)
async def read_tournament(
    tournament_id: int, db: AsyncSession = Depends(get_db)
) -> TournamentView:
    return await _view(db, await _load(db, tournament_id))


@router.delete("/{tournament_id}", response_model=DeleteTournamentResponse)
async def delete_tournament(
    tournament_id: int, db: AsyncSession = Depends(get_db)
) -> DeleteTournamentResponse:
    """Delete a tournament in ANY status — abandon an in-flight bracket or
    remove a history entry. The battles table (determinism cache) and the
    creatures' win/loss records are untouched."""
    t = await _load(db, tournament_id)
    await db.delete(t)
    return DeleteTournamentResponse(tournament_id=tournament_id)


@router.post("/{tournament_id}/matches/{match_id}/predict", response_model=TournamentView)
async def predict(
    tournament_id: int, match_id: str, body: PredictRequest,
    db: AsyncSession = Depends(get_db),
) -> TournamentView:
    """"Who do you think will win?" — locked in before the match resolves (§7)."""
    async with _bracket_lock(tournament_id):
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
        await db.commit()  # inside the lock — the next writer must see this pick
        return await _view(db, t)


@router.post("/{tournament_id}/matches/{match_id}/resolve", response_model=ResolveResponse)
async def resolve(
    tournament_id: int, match_id: str, db: AsyncSession = Depends(get_db)
) -> ResolveResponse:
    """Run the match, advance the bracket, and crown a champion at the end.

    Battles are permanently cached by canonical key, so a matchup that has
    happened before in ANY tournament replays instantly with the same winner.
    """
    # The lock spans load -> LLM -> commit: a double-tap waits, re-reads the
    # committed winner, and takes the free replay path instead of double-
    # spending the LLM call or double-counting the win/loss records.
    async with _bracket_lock(tournament_id):
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
        _battle_records(winner, loser, row)

        match["winner"] = winner_id
        match["battle_id"] = row.id
        if match["predicted"] is not None:
            match["prediction_correct"] = match["predicted"] == winner_id
            # The Oracle score: predictions are the player's skill expression
            # in a deterministic game, so every call feeds a lifetime tally
            # and a streak in Profile.settings (JSON — no migration).
            profile = await get_profile(db)
            settings = dict(profile.settings or {})
            settings["calls_made"] = int(settings.get("calls_made", 0)) + 1
            if match["prediction_correct"]:
                award_xp(profile, XP_CORRECT_PREDICTION)
                settings["calls_right"] = int(settings.get("calls_right", 0)) + 1
                settings["call_streak"] = int(settings.get("call_streak", 0)) + 1
                settings["best_call_streak"] = max(
                    int(settings.get("best_call_streak", 0)), settings["call_streak"]
                )
            else:
                settings["call_streak"] = 0
            profile.settings = settings

        bracket_svc.advance(bracket, round_index, match_index, winner_id)

        # Semifinals just completed -> both finalists known: pre-generate the
        # championship key art now so the ~74s render hides inside the final
        # prediction + battle and the ceremony never waits (AI_CONTRACTS §3).
        final = bracket["rounds"][-1]["matches"][0]
        if (final.get("a") and final.get("b") and final.get("winner") is None
                and not bracket.get("final_art") and ai.ai_enabled()):
            bracket["final_art"] = "pending"
            creatures_api.spawn(_final_art_task(t.id, final["a"], final["b"]), f"final-art:{t.id}")

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
            # A perfect bracket — every match called, every call right — is
            # the player's own championship.
            all_matches = [m for r in bracket["rounds"] for m in r["matches"]]
            if all_matches and all(
                m.get("predicted") is not None and m.get("prediction_correct")
                for m in all_matches
            ):
                profile = await get_profile(db)
                settings = dict(profile.settings or {})
                settings["perfect_brackets"] = int(settings.get("perfect_brackets", 0)) + 1
                profile.settings = settings

        t.bracket = bracket
        await db.commit()  # inside the lock — see _bracket_lock
        return ResolveResponse(
            battle=_battle_view(row, match, cached=cached),
            tournament=await _view(db, t),
        )


async def _final_art_task(tournament_id: int, a_id: int, b_id: int) -> None:
    """Background finals key-art render; owns its session (request one closes)."""
    from ..db import session_factory

    # Load, CLOSE the session, render sessionless, reopen to write: holding a
    # SQLite transaction across the ~74s render blocked every other writer
    # (this is what stranded creatures at "generating", 2026-08-09).
    async with session_factory()() as db:
        fa = await db.get(Creature, a_id)
        fb = await db.get(Creature, b_id)
        exists = (await db.get(Tournament, tournament_id)) is not None
    if not (fa and fb and exists):
        return
    path = await images.generate_championship_art(fa, fb)
    # Same lock as predict/resolve: this write races the final match's resolve
    # by design (the render hides inside it), and an unserialized last-committer
    # would either lose the final's winner or strand final_art at "pending".
    async with _bracket_lock(tournament_id), session_factory()() as db:
        t = await db.get(Tournament, tournament_id)
        if t is None:
            return
        bracket = copy.deepcopy(t.bracket)
        bracket["final_art"] = path  # None -> ceremony uses composited finale
        t.bracket = bracket
        await db.commit()
