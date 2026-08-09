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

import asyncio
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
    Strict,
)
from . import library

log = logging.getLogger("chimera.generation")

# The real gpt-5.1 path runs whenever ai.ai_enabled(); the deterministic
# local stub covers tests and keyless dev.


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


SYSTEM_PROMPT = (
    "You are the creature engine for Chimera Creator, a game where a "
    "7-year-old fuses four real, extinct, or mythical creatures into one "
    "spectacular new species. Invent ONE coherent species — never four "
    "animals stitched together. Map each source to body systems in the "
    "anatomy plan. The best abilities fuse TWO sources (Shark + Electric Eel "
    "= Thunder Bite), never one source alone restated. Every creature needs "
    "real weaknesses that follow from its body — resist 'awesome at "
    "everything'. Stats are 0-100 with an honest spread, not all 90s; size "
    "must reflect the actual fused anatomy. environment_affinities must "
    "follow from the anatomy (a deep-sea build should suffer in desert "
    "ruins). visual_spec must be a complete physical description an image "
    "model can paint: body plan, colors, textures, signature features from "
    "all four sources — no lore, no text-in-image instructions. Describe "
    "ONLY the creature's own body: never its surroundings, backdrop, "
    "weather, or what it stands on — it will be rendered isolated on a "
    "transparent background and composited onto a game stage. "
    "Kid-readable language everywhere: short, punchy, epic but never gory "
    "(defeated/knocked out, never killed; no blood). Names must be "
    "pronounceable by a child, exciting, and hint at 1-2 component traits."
)


def _source_briefs(slugs: list[str]) -> str:
    lines = []
    for slug in slugs:
        raw = library.raw_source(slug)
        if raw:
            traits = raw.get("traits") or {}
            head = (
                f"{raw.get('name', slug)} [{raw.get('category', '?')}] — "
                f"scale {raw.get('scale', '?')}/10 ({raw.get('real_size', '?')})"
            )
            moves = ", ".join(raw.get("movement_types") or [])
            bits = [
                head,
                f"iconic: {traits.get('iconic_appearance', '?')}",
                f"weapon: {traits.get('signature_weapon', '?')}",
                f"movement: {traits.get('movement', '?')} ({moves})",
                f"defense: {traits.get('defense', '?')}",
            ]
            if traits.get("mythic_power"):
                bits.append(f"mythic power: {traits['mythic_power']}")
            bits.append(f"looks: {raw.get('visual_hint', '?')}")
            lines.append("- " + "; ".join(bits))
        else:
            lines.append(f"- {library.display_name(slug)}")
    return "\n".join(lines)


async def generate_creature(sources: list[str], extra_instructions: str = "") -> CreatureRecord:
    """Produce a full creature record from four source slugs.

    Real path: gpt-5.1 structured output (docs/AI_CONTRACTS.md §1, ~16s),
    enriched with the authored library traits so interpretation stays stable.
    Stub path (tests / keyless dev): deterministic local record.

    `extra_instructions` (seed pipeline only) is appended verbatim to the user
    message; the default empty string keeps the runtime prompt byte-identical.
    """
    from . import ai

    if not ai.ai_enabled():
        log.info("generation: STUB record for %s", sources)
        return build_stub_record(sources)

    user = (
        "Create a chimera fused from exactly these four sources:\n"
        f"{_source_briefs(sources)}\n\n"
        "Remember: one coherent species, fused abilities, honest weaknesses."
    )
    if extra_instructions:
        user += f"\n\n{extra_instructions}"
    record = await ai.structured(SYSTEM_PROMPT, user, CreatureRecord, name="chimera")
    log.info("generation: gpt-5.1 record %r for %s", record.name, sources)
    return record


# -- streaming generation (Fusion Wait experience) ----------------------------

#: creature_id -> partial fields revealed so far ("name", "title", "rarity",
#: "core_stats", "abilities_count") plus "image_started" once the hero render
#: task is actually running. Read by GET /api/creatures/{id} while the record
#: streams and while the render is in flight. In-memory is correct here:
#: single-player, single-process, and the map is only a progress mirror of
#: work in flight.
PROGRESS: dict[int, dict] = {}

_FIELD_RE = {
    "name": re.compile(r'"name"\s*:\s*"([^"]{1,120})"'),
    "title": re.compile(r'"title"\s*:\s*"([^"]{1,160})"'),
    "rarity": re.compile(r'"rarity"\s*:\s*"(Uncommon|Rare|Epic|Legendary)"'),
    "visual_spec": re.compile(r'"visual_spec"\s*:\s*"((?:[^"\\]|\\.){20,4000})"\s*[,}]'),
}
_CORE_RE = re.compile(
    r'"core_stats"\s*:\s*\{[^{}]*?"power"\s*:\s*(\d+)[^{}]*?"speed"\s*:\s*(\d+)'
    r'[^{}]*?"armor"\s*:\s*(\d+)[^{}]*?"size"\s*:\s*(\d+)'
    r'[^{}]*?"special_name"\s*:\s*"([^"]+)"[^{}]*?"special"\s*:\s*(\d+)'
)
_ABILITY_NAME_RE = re.compile(r'"abilities"\s*:\s*\[(.*)', re.DOTALL)


def _extract_partial(buf: str) -> dict:
    """Best-effort field extraction from a growing JSON document."""
    out: dict = {}
    for key, rx in _FIELD_RE.items():
        m = rx.search(buf)
        if m:
            out[key] = m.group(1)
    m = _CORE_RE.search(buf)
    if m:
        out["core_stats"] = {
            "power": int(m.group(1)), "speed": int(m.group(2)),
            "armor": int(m.group(3)), "size": int(m.group(4)),
            "special_name": m.group(5), "special": int(m.group(6)),
        }
    m = _ABILITY_NAME_RE.search(buf)
    if m:
        names = re.findall(r'"name"\s*:\s*"([^"]{1,80})"', m.group(1))
        if names:
            out["ability_names"] = names[:4]
    return out


async def generate_creature_streaming(
    creature_id: int, sources: list[str], on_visual_spec=None
) -> CreatureRecord:
    """Stream the record, mirroring partial fields into PROGRESS[creature_id].

    `on_visual_spec(spec)` fires the moment visual_spec fully parses — the
    hero render starts there, not when the record finishes (~10s earlier).
    Caller owns persistence and PROGRESS cleanup.
    """
    import json

    from . import ai

    if not ai.ai_enabled():
        return build_stub_record(sources)

    user = (
        "Create a chimera fused from exactly these four sources:\n"
        f"{_source_briefs(sources)}\n\n"
        "Remember: one coherent species, fused abilities, honest weaknesses."
    )
    schema = CreatureRecord.model_json_schema()
    # Stall watchdog: a hung connection can stall before the first chunk just
    # as easily as mid-stream (observed in the wild: creature stuck at
    # "generating" with zero streamed fields). No single gap — including
    # opening the stream — may exceed STALL_S; the caller's except path marks
    # the creature failed/retryable.
    STALL_S = 45
    try:
        stream = await asyncio.wait_for(
            ai.client().chat.completions.create(
                model=ai.TEXT_MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": user}],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "chimera", "strict": True,
                                                 "schema": schema}},
                stream=True,
            ),
            timeout=STALL_S,
        )
    except TimeoutError as exc:
        raise RuntimeError(f"record stream failed to open within {STALL_S}s") from exc
    buf = ""
    spec_fired = False
    it = stream.__aiter__()
    while True:
        try:
            chunk = await asyncio.wait_for(it.__anext__(), timeout=STALL_S)
        except StopAsyncIteration:
            break
        except TimeoutError as exc:
            raise RuntimeError(
                f"record stream stalled >{STALL_S}s after {len(buf)} chars"
            ) from exc
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if not delta:
            continue
        buf += delta
        partial = _extract_partial(buf)
        if partial:
            # Merge, never replace: start_hero drops "image_started" into this
            # entry mid-stream and it must survive every later chunk.
            PROGRESS.setdefault(creature_id, {}).update(partial)
        if not spec_fired and on_visual_spec and "visual_spec" in partial:
            spec_fired = True
            spec = json.loads(f'"{partial["visual_spec"]}"' if "\\" in partial["visual_spec"]
                              else json.dumps(partial["visual_spec"]))
            await on_visual_spec(spec)
    record = CreatureRecord.model_validate(json.loads(buf))
    log.info("generation: streamed record %r for %s", record.name, sources)
    return record


class _NameOnly(Strict):
    name: str
    title: str


async def reroll_name(sources: list[str], current_name: str) -> tuple[str, str]:
    """Name reroll (spec §11): new name/title only, stats untouched."""
    from . import ai

    if not ai.ai_enabled():
        record = build_stub_record(sources, nonce=f"reroll:{current_name}")
        for attempt in range(1, 12):
            if record.name != current_name:
                break
            record = build_stub_record(sources, nonce=f"reroll:{current_name}:{attempt}")
        return record.name, record.title

    names = ", ".join(library.display_name(s) for s in sources)
    result = await ai.structured(
        SYSTEM_PROMPT,
        f"A chimera fused from {names} is currently named {current_name!r}. "
        "Give it a DIFFERENT species name (and matching epic title) in the "
        "same universe style — pronounceable by a 7-year-old, hinting at its "
        "components. Do not reuse the current name or a trivial variant.",
        _NameOnly,
        name="rename",
    )
    return result.name, result.title
