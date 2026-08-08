"""Bracket construction and advancement (spec §15).

Eight entrants: Quarterfinals -> Semifinals -> Championship. Every match gets a
random environment at build time, stored on the match so replays and the
determinism cache always see the same (a, b, environment) triple.
"""
from __future__ import annotations

import random

from . import library

ROUND_NAMES = ("Quarterfinals", "Semifinals", "Championship")
ENTRANT_COUNT = 8


def match_id(round_index: int, index: int) -> str:
    return f"r{round_index}m{index}"


def build_bracket(entrant_ids: list[int], rng: random.Random | None = None) -> dict:
    """Seed the 8 entrants into a full, pre-shaped bracket.

    Later rounds exist immediately with `a`/`b` as null so the Bracket screen can
    draw the whole tree (and its "TBD" slots) from one payload.
    """
    rng = rng or random.Random()
    envs = library.environment_slugs()

    rounds = []
    pairs = [(entrant_ids[i], entrant_ids[i + 1]) for i in range(0, ENTRANT_COUNT, 2)]
    for round_index, name in enumerate(ROUND_NAMES):
        count = ENTRANT_COUNT // (2 ** (round_index + 1))
        matches = []
        for i in range(count):
            a, b = pairs[i] if round_index == 0 else (None, None)
            matches.append({
                "id": match_id(round_index, i),
                "a": a,
                "b": b,
                "winner": None,
                "battle_id": None,
                "environment": rng.choice(envs),
                "predicted": None,
                "prediction_correct": None,
            })
        rounds.append({"name": name, "matches": matches})
    return {"rounds": rounds}


def find_match(bracket: dict, wanted: str) -> tuple[int, int, dict] | None:
    for r, rnd in enumerate(bracket.get("rounds", [])):
        for m, match in enumerate(rnd.get("matches", [])):
            if match.get("id") == wanted:
                return r, m, match
    return None


def advance(bracket: dict, round_index: int, match_index: int, winner_id: int) -> None:
    """Drop the winner into its slot in the next round (top match feeds slot a)."""
    rounds = bracket["rounds"]
    if round_index + 1 >= len(rounds):
        return
    nxt = rounds[round_index + 1]["matches"][match_index // 2]
    nxt["a" if match_index % 2 == 0 else "b"] = winner_id


def is_complete(bracket: dict) -> bool:
    final = bracket["rounds"][-1]["matches"][0]
    return final.get("winner") is not None


def champion_id(bracket: dict) -> int | None:
    return bracket["rounds"][-1]["matches"][0].get("winner")
