"""Creature generation.

===========================  STUB IMPLEMENTATION  ===========================
`generate_creature()` is the real interface and is already async, but today it
returns a locally-synthesised record from `build_stub_record()`. Nothing here
touches an API key. Swap the body of `generate_creature()` for the gpt-5.1
structured-output call (schema == schemas.CreatureRecord, system prompt per
spec §10/§23) and the rest of the app needs no changes.

The stub is *deterministic in the source slugs*: the same four sources always
produce the same record, which keeps the frontend and the tests stable while
the real generator is offline.
============================================================================
"""
from __future__ import annotations

import hashlib
import logging
import random
import re

from ..schemas import (
    ENVIRONMENT_SLUGS,
    Ability,
    CoreStats,
    CreatureRecord,
    EnvironmentAffinities,
    SimProfile,
)
from . import library

log = logging.getLogger("chimera.generation")

#: Flip to False when the real gpt-5.1 path lands.
IS_STUB = True


def _rng(*parts: str) -> random.Random:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def _letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower()) or "beast"


# -- naming (spec §11) --------------------------------------------------------

HEAD_LEN = 4
TAILS = ("drake", "don", "fin", "maw", "claw", "wing", "back", "horn", "surge", "tusk")
TITLE_ADJECTIVES = (
    "Thundered", "Tidal", "Ironclad", "Emberborn", "Frostbound",
    "Skyriven", "Deepwater", "Stormcut", "Molten", "Everwaking",
)
TITLE_NOUNS = (
    "Leviathan", "Sovereign", "Colossus", "Vanguard", "Warden",
    "Titan", "Sentinel", "Marauder", "Herald", "Bulwark",
)
ROLES = (
    "Bruiser / Area Control", "Skirmisher / Ambush", "Tank / Zone Denial",
    "Striker / Burst Damage", "Hunter / Pursuit", "Controller / Terrain",
)


def _species_name(rng: random.Random, names: list[str]) -> str:
    head = _letters(names[0])[:HEAD_LEN].capitalize()
    tail_src = _letters(names[1])
    tail = tail_src[-4:] if len(tail_src) > 5 else rng.choice(TAILS)
    first = f"{head}{tail}"
    if rng.random() < 0.55:
        second = _letters(names[2])[:3].capitalize() + rng.choice(TAILS)
        return f"{first} {second}"
    return first


def _title(rng: random.Random) -> str:
    return f"The {rng.choice(TITLE_ADJECTIVES)} {rng.choice(TITLE_NOUNS)}"


# -- abilities (spec §13) -----------------------------------------------------

ABILITY_PATTERNS = (
    ("{a} Surge", "Unleashes a huge burst of energy that knocks enemies backward!"),
    ("{a} Smash", "Slams the ground hard enough to send a shockwave rolling out!"),
    ("Spike {b}", "Raises sharp armored plates to block the next big attack!"),
    ("Deep {b} Charge", "Dashes forward incredibly fast and hits first!"),
    ("{a} Bite", "Clamps down with a bone-rattling bite that will not let go!"),
    ("{b} Veil", "Vanishes for a moment, then strikes from somewhere new!"),
    ("Tidal {b}", "Throws up a towering wall of water to shove enemies away!"),
    ("{a} Roar", "Lets out a roar so loud that smaller creatures scatter!"),
)
ABILITY_WORDS = (
    "Thunder", "Ember", "Frost", "Storm", "Venom", "Gale", "Quake", "Shadow",
    "Wall", "Wave", "Fang", "Talon", "Crest", "Sting", "Shell",
)


def _abilities(rng: random.Random, names: list[str]) -> list[Ability]:
    """3-4 abilities; each fuses TWO sources (the synergy rule, spec §10)."""
    patterns = rng.sample(ABILITY_PATTERNS, k=rng.randint(3, 4))
    pairs = [
        (names[0], names[1]), (names[2], names[3]),
        (names[0], names[2]), (names[1], names[3]),
    ]
    rng.shuffle(pairs)
    out: list[Ability] = []
    for i, (pattern, blurb) in enumerate(patterns):
        word_a, word_b = rng.sample(ABILITY_WORDS, k=2)
        out.append(
            Ability(
                name=pattern.format(a=word_a, b=word_b),
                blurb=blurb,
                sources=list(pairs[i % len(pairs)]),
            )
        )
    return out


# -- stats (spec §12) ---------------------------------------------------------

SPECIAL_NAMES = ("Venom", "Flight", "Electricity", "Fire", "Stealth", "Bite", "Endurance")


def _core_stats(rng: random.Random) -> CoreStats:
    # Honest spread: one standout, one soft spot, the rest middling. Never all 90s.
    values = [rng.randint(45, 96) for _ in range(5)]
    values[rng.randrange(5)] = rng.randint(88, 97)
    values[rng.randrange(5)] = rng.randint(32, 58)
    return CoreStats(
        power=values[0], speed=values[1], armor=values[2], size=values[3],
        special_name=rng.choice(SPECIAL_NAMES), special=values[4],
    )


def _sim_profile(rng: random.Random, cs: CoreStats) -> SimProfile:
    """Richer hidden view derived from the visible stats plus jitter (§12, §18)."""

    def near(base: int, spread: int = 18) -> int:
        return max(0, min(100, base + rng.randint(-spread, spread)))

    return SimProfile(
        land_speed=near(cs.speed),
        swim_speed=near(cs.speed),
        flight_speed=near(max(10, cs.speed - 25)),
        bite_force=near(cs.power),
        armor_rating=near(cs.armor),
        intelligence=near(60),
        endurance=near((cs.armor + cs.size) // 2),
        regeneration=near(35),
        attack_range=near(cs.special),
        maneuverability=near(max(10, 100 - cs.size)),
    )


def _affinities(rng: random.Random) -> EnvironmentAffinities:
    """Every creature gets one home turf and one place it hates (§10 weaknesses)."""
    scores = {slug: rng.choice([-1, 0, 0, 1, 1, 2]) for slug in ENVIRONMENT_SLUGS}
    home, hostile = rng.sample(list(ENVIRONMENT_SLUGS), k=2)
    scores[home] = 2
    scores[hostile] = -2
    return EnvironmentAffinities(**scores)


STRENGTH_PHRASES = {
    "power": "Hits harder than almost anything its size",
    "speed": "Closes the distance before you can blink",
    "armor": "Shrugs off the first big hit every time",
    "size": "Big enough to shove smaller fighters aside",
    "special": "Its signature power turns fights around",
}
WEAKNESS_PHRASES = {
    "power": "Its attacks lack real punching power",
    "speed": "Slow to turn once it commits to a charge",
    "armor": "Thin plating — a solid hit really lands",
    "size": "Small enough to get overpowered up close",
    "special": "Its special power drains fast and needs a rest",
}


def _strengths_weaknesses(cs: CoreStats) -> tuple[list[str], list[str]]:
    ranked = sorted(
        (("power", cs.power), ("speed", cs.speed), ("armor", cs.armor),
         ("size", cs.size), ("special", cs.special)),
        key=lambda kv: kv[1],
        reverse=True,
    )
    strengths = [STRENGTH_PHRASES[k] for k, _ in ranked[:2]]
    weaknesses = [WEAKNESS_PHRASES[k] for k, _ in ranked[-2:]]
    return strengths, weaknesses


def _rarity(cs: CoreStats) -> str:
    total = cs.power + cs.speed + cs.armor + cs.size + cs.special
    if total >= 400:
        return "Legendary"
    if total >= 350:
        return "Epic"
    if total >= 300:
        return "Rare"
    return "Uncommon"


# -- the stub record ----------------------------------------------------------

def build_stub_record(sources: list[str], nonce: str = "") -> CreatureRecord:
    """A deterministic, schema-valid CreatureRecord. No network, no API keys.

    `nonce` exists so the name-reroll endpoint can walk to a different name
    without becoming non-deterministic.
    """
    rng = _rng("chimera-stub-v1", nonce, *sources)
    names = [library.display_name(s) for s in sources]

    cs = _core_stats(rng)
    strengths, weaknesses = _strengths_weaknesses(cs)
    joined = ", ".join(names)

    return CreatureRecord(
        name=_species_name(rng, names),
        title=_title(rng),
        anatomy_plan=(
            f"A single coherent species: the frame and stance come from {names[0]}, "
            f"the defensive structures from {names[1]}, the power system from "
            f"{names[2]}, and the hunting hardware from {names[3]}. One animal, "
            "not four animals stitched together."
        ),
        role=rng.choice(ROLES),
        core_stats=cs,
        abilities=_abilities(rng, names),
        strengths=strengths,
        weaknesses=weaknesses,
        environment_affinities=_affinities(rng),
        sim_profile=_sim_profile(rng, cs),
        visual_spec=(
            f"Full-body creature render fusing {joined}. Deep slate and gunmetal hide "
            "with bioluminescent seams, layered armored plating along the spine, "
            "wet-looking musculature, dramatic rim lighting, photoreal movie-monster "
            "detail, transparent background, absolutely no text."
        ),
        rarity=_rarity(cs),
        fun_fact=(
            f"It can hold its breath long enough to walk clear across a lagoon floor — "
            f"a trick it inherited from the {names[3].lower()} half."
        ),
    )


async def generate_creature(sources: list[str]) -> CreatureRecord:
    """Produce a full creature record from four source slugs.

    REAL IMPLEMENTATION (todo): gpt-5.1 chat.completions with
    response_format=json_schema built from `CreatureRecord`, system prompt from
    spec §10 + §23 safety rules, ~16s. Degrade to gemini-3-flash, then to
    `build_stub_record` — never leave the player without a creature.
    """
    if IS_STUB:
        log.info("generation: STUB record for %s", sources)
        return build_stub_record(sources)
    raise NotImplementedError("real gpt-5.1 generation not wired yet")  # pragma: no cover


async def reroll_name(sources: list[str], current_name: str) -> tuple[str, str]:
    """Name reroll (spec §11). Deterministic chain: same input -> same next name.

    Walks the nonce until the name actually changes — a reroll that hands back
    the name you just rejected reads as a broken button.
    """
    record = build_stub_record(sources, nonce=f"reroll:{current_name}")
    for attempt in range(1, 12):
        if record.name != current_name:
            break
        record = build_stub_record(sources, nonce=f"reroll:{current_name}:{attempt}")
    return record.name, record.title
