"""Battle resolution.

===========================  STUB IMPLEMENTATION  ===========================
`resolve_battle()` is the real interface. Today it computes the outcome locally
from the saved profiles plus a sha256 of the canonical key — no API key, no
network. Swap the body for the gpt-5.1 structured-output call (schema ==
schemas.BattleResult, prompt per spec §20) and callers need no changes.
============================================================================

Determinism (ARCHITECTURE.md, spec §20): outcome = f(creatureA, creatureB,
environment). The pair is normalized to (min_id, max_id) so A-vs-B and B-vs-A
are the same question, the answer is computed once, and `Battle.canonical_key`
stores it forever. The stub honours the same promise, so brackets behave
identically before and after the real engine lands.
"""
from __future__ import annotations

import hashlib
import logging

from ..models import Creature
from ..schemas import BattleReason, BattleResult, HealthRemaining
from . import library

log = logging.getLogger("chimera.battle")

MAX_HEALTH = 1000


def canonical_key(a_id: int, b_id: int, environment: str) -> str:
    """"minId:maxId:env" — the permanent cache key for a matchup."""
    lo, hi = (a_id, b_id) if a_id <= b_id else (b_id, a_id)
    return f"{lo}:{hi}:{environment}"


def canonical_pair(a: Creature, b: Creature) -> tuple[Creature, Creature]:
    """Order a matchup by id so both call orders produce one identical battle."""
    return (a, b) if a.id <= b.id else (b, a)


# -- scoring ------------------------------------------------------------------

def _stat(c: Creature, key: str, default: int = 50) -> int:
    value = (c.core_stats or {}).get(key, default)
    return int(value) if isinstance(value, (int, float)) else default


def _sim(c: Creature, key: str, default: int = 50) -> int:
    value = (c.sim_profile or {}).get(key, default)
    return int(value) if isinstance(value, (int, float)) else default


def _affinity(c: Creature, environment: str) -> int:
    value = (c.environment_affinities or {}).get(environment, 0)
    return int(value) if isinstance(value, (int, float)) else 0


def _matchup_score(c: Creature, environment: str) -> float:
    """Never a flat stat sum (spec §20) — terrain and the hidden profile matter."""
    visible = (
        0.32 * _stat(c, "power")
        + 0.20 * _stat(c, "speed")
        + 0.24 * _stat(c, "armor")
        + 0.12 * _stat(c, "size")
        + 0.12 * _stat(c, "special")
    )
    hidden = 0.18 * (
        _sim(c, "bite_force") + _sim(c, "armor_rating")
        + _sim(c, "endurance") + _sim(c, "maneuverability")
    ) / 4
    return visible + hidden + _affinity(c, environment) * 7.0


def _jitter(key: str) -> float:
    """A stable ±10 nudge so raw stat totals do not decide every fight.

    Derived from the canonical key, so it is constant for a given matchup and
    the determinism promise still holds.
    """
    digest = hashlib.sha256(f"chimera-battle-v1:{key}".encode()).hexdigest()
    return (int(digest[:8], 16) % 2001) / 100.0 - 10.0


# -- child-facing explanation -------------------------------------------------

#: `icon` is an asset-slot keyword, never an emoji (ARCHITECTURE.md non-negotiable).
REASON_TEMPLATES = {
    "armor": ("Stronger Armor", "{loser} could not break through those plates."),
    "speed": ("Faster Start", "{winner} landed the first major hit."),
    "power": ("Raw Power", "Every hit from {winner} shook the whole arena."),
    "size": ("Bigger Frame", "{winner} simply shoved {loser} out of position."),
    "special": ("Signature Power", "{winner}'s special attack changed the fight."),
    "environment": ("Home Ground", "The {environment} suited {winner} much better."),
    "endurance": ("Longer Stamina", "{loser} tired out first and slowed down."),
    "range": ("Longer Reach", "{winner} kept hitting from outside {loser}'s reach."),
}
FALLBACK_ORDER = ("power", "armor", "speed", "environment", "size", "special")


def _advantages(winner: Creature, loser: Creature, environment: str) -> list[str]:
    deltas = {
        "armor": _stat(winner, "armor") - _stat(loser, "armor"),
        "speed": _stat(winner, "speed") - _stat(loser, "speed"),
        "power": _stat(winner, "power") - _stat(loser, "power"),
        "size": _stat(winner, "size") - _stat(loser, "size"),
        "special": _stat(winner, "special") - _stat(loser, "special"),
        "environment": (_affinity(winner, environment) - _affinity(loser, environment)) * 12,
        "endurance": _sim(winner, "endurance") - _sim(loser, "endurance"),
        "range": _sim(winner, "attack_range") - _sim(loser, "attack_range"),
    }
    ranked = [k for k, v in sorted(deltas.items(), key=lambda kv: kv[1], reverse=True) if v > 0]
    for key in FALLBACK_ORDER:  # a clean sweep still needs three things to say
        if len(ranked) >= 3:
            break
        if key not in ranked:
            ranked.append(key)
    return ranked[:3]


def _reasons(winner: Creature, loser: Creature, environment: str) -> list[BattleReason]:
    env_name = library.display_name(environment)
    out = []
    for key in _advantages(winner, loser, environment):
        title, blurb = REASON_TEMPLATES[key]
        out.append(
            BattleReason(
                icon=key,
                title=title,
                blurb=blurb.format(winner=winner.name, loser=loser.name, environment=env_name),
            )
        )
    return out


def _beats(winner: Creature, loser: Creature, environment: str) -> list[str]:
    env_name = library.display_name(environment)
    return [
        f"The two chimeras square off across the {env_name.lower()}.",
        f"{loser.name} opens with a charge, forcing {winner.name} to give ground.",
        f"{winner.name} plants its feet and absorbs the hit on its armor.",
        f"A signature strike from {winner.name} turns the fight around.",
        f"{loser.name} is driven back and knocked out of the arena.",
    ]


def _narrative(winner: Creature, loser: Creature, environment: str) -> str:
    env_name = library.display_name(environment)
    return (
        f"{loser.name} charged first across the {env_name.lower()}, but {winner.name} "
        f"took the hit square on its plating and never lost its footing. When the fight "
        f"swung back the other way, {winner.name} landed one enormous strike and "
        f"{loser.name} was knocked out cold."
    )


# -- the real engine (docs/AI_CONTRACTS.md §2) --------------------------------

BATTLE_SYSTEM = (
    "You are the battle judge for Chimera Creator, a game for a 7-year-old. "
    "Given two creature profiles and an environment, decide who probably "
    "wins and why. NEVER decide by comparing stat totals — reason about "
    "concrete interactions: mobility in this terrain, reach, armor versus "
    "the opponent's weapons, stamina, elemental effects, whether one can "
    "force the fight into its preferred zone, and each creature's listed "
    "weaknesses. The environment must matter. Reasons: exactly three, each "
    "kid-readable (title 4 words max, blurb 12 words max), each naming a "
    "concrete trait or environment interaction. Beats: 4-6 short dramatic "
    "sentences (opening, first advantage, counter, turning point, finisher). "
    "Narrative: 2-3 sentences, epic monster action, never gory — creatures "
    "are defeated, knocked out, driven back; nothing dies or bleeds. "
    "Health: the loser ends at 0; the winner keeps 150-950 of 1000 "
    "proportional to how close the fight was. Confidence 0.5-0.97."
)


def _profile_block(label: str, c: Creature) -> str:
    import json

    return (
        f"CREATURE {label} — {c.name!r} (id {c.id})\n"
        f"core stats: {json.dumps(c.core_stats)}\n"
        f"abilities: {json.dumps(c.abilities)}\n"
        f"strengths: {c.strengths}\nweaknesses: {c.weaknesses}\n"
        f"hidden sim profile: {json.dumps(c.sim_profile)}\n"
        f"environment affinities (-2..+2): {json.dumps(c.environment_affinities)}\n"
    )


def _environment_block(environment: str) -> str:
    import json

    raw = library.raw_environment(environment)
    name = library.display_name(environment)
    if not raw:
        return f"ENVIRONMENT: {name}"
    return (
        f"ENVIRONMENT: {raw.get('name', name)}\n"
        f"conditions: {json.dumps(raw.get('sim', {}))}\n"
        f"known dynamics: {raw.get('advantages_hint', '')}"
    )


async def _resolve_llm(lo: Creature, hi: Creature, environment: str, key: str) -> BattleResult:
    from . import ai

    user = (
        f"{_profile_block('A', lo)}\n{_profile_block('B', hi)}\n"
        f"{_environment_block(environment)}\n\n"
        f"Decide the battle. Set winner_slug_or_id to the winner's id as a "
        f"string: {lo.id!r} for creature A or {hi.id!r} for creature B. "
        "health_remaining.a belongs to creature A, health_remaining.b to "
        "creature B; the loser's health is 0."
    )
    result = await ai.structured(BATTLE_SYSTEM, user, BattleResult, name="battle")

    valid = {str(lo.id), str(hi.id)}
    if result.winner_slug_or_id not in valid:
        by_name = {lo.name: str(lo.id), hi.name: str(hi.id)}
        fixed = by_name.get(result.winner_slug_or_id)
        if fixed is None:
            raise ValueError(f"winner {result.winner_slug_or_id!r} is neither creature")
        result.winner_slug_or_id = fixed
    # The loser is at 0 by contract; enforce it so the UI never shows a
    # half-dead winner on both sides.
    if result.winner_slug_or_id == str(lo.id):
        result.health_remaining.b = 0
        result.health_remaining.a = max(150, min(950, result.health_remaining.a))
    else:
        result.health_remaining.a = 0
        result.health_remaining.b = max(150, min(950, result.health_remaining.b))
    log.info("battle: gpt-5.1 resolve %s -> winner %s (%.2f)",
             key, result.winner_slug_or_id, result.confidence)
    return result


# -- the engine ---------------------------------------------------------------

async def resolve_battle(a: Creature, b: Creature, environment: str) -> BattleResult:
    """Decide (a, b, environment). Callers must persist the result under
    `canonical_key(a.id, b.id, environment)` and read the cache first.

    The returned BattleResult is expressed in CANONICAL order: `health_remaining.a`
    belongs to the lower-id creature. Callers store the battle row the same way.

    REAL IMPLEMENTATION (todo): gpt-5.1 chat.completions, response_format=
    json_schema from `BattleResult`, both saved profiles + the environment card
    in the prompt (spec §20 steps 1-6). Falls back to this local scorer whenever
    the model is unavailable — a tournament must never strand.
    """
    from . import ai

    lo, hi = canonical_pair(a, b)
    key = canonical_key(a.id, b.id, environment)

    if ai.ai_enabled():
        try:
            return await _resolve_llm(lo, hi, environment, key)
        except Exception as exc:  # noqa: BLE001 - a tournament must never strand
            log.warning("battle: LLM resolve failed for %s (%s) — local fallback",
                        key, str(exc)[:200])

    log.info("battle: STUB resolve %s", key)

    score_lo = _matchup_score(lo, environment) + _jitter(key)
    score_hi = _matchup_score(hi, environment)
    winner, loser = (lo, hi) if score_lo >= score_hi else (hi, lo)

    margin = abs(score_lo - score_hi)
    confidence = round(min(0.97, 0.52 + margin / 60.0), 2)
    winner_health = int(min(MAX_HEALTH, 200 + confidence * 780))

    return BattleResult(
        winner_slug_or_id=str(winner.id),
        confidence=confidence,
        reasons=_reasons(winner, loser, environment),
        narrative=_narrative(winner, loser, environment),
        beats=_beats(winner, loser, environment),
        health_remaining=HealthRemaining(
            a=winner_health if winner.id == lo.id else 0,
            b=winner_health if winner.id == hi.id else 0,
        ),
    )
