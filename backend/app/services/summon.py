"""Summon New Creature (POST /api/library/summon, ARCHITECTURE.md 'hybrid').

Henry types ANY animal — real, extinct, mythical, or misspelled — and this
module either matches it to the library or conjures a brand-new custom part:

1. Local resolution first (free, instant): normalized exact match against
   slugs, names, and the 661 authored aliases. One hit -> matched; several
   hits (the deliberate ambiguity pairs, e.g. "quetzalcoatl") -> disambiguate.
2. No local hit -> the gpt-5.1 summon resolver decides: library misspelling,
   a genuine new creature (full kid-readable part record), or a playful
   kid-safe redirect (never a scold, never a hard error).
3. New parts persist to the custom_parts table, merge into the live library
   registry immediately (usable in a fusion at once), and the gpt-image-1.5
   portrait renders in the background in the exact pregen-portrait style.
"""
from __future__ import annotations

import asyncio
import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CustomPart, ImageStatus
from ..schemas import SourceCreature, SummonResolution, SummonResponse
from . import images, library

log = logging.getLogger("chimera.summon")

REDIRECT_FALLBACK = (
    "The summoning circle only answers to creatures! Try a dinosaur, "
    "a deep-sea beast, or something straight out of legend."
)


# -- normalization + local resolution ------------------------------------------

def normalize(text: str) -> str:
    """Kid-typing tolerant: lowercase, collapse punctuation/spacing."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _slugify(name: str) -> str:
    """Hyphenated, matching the authored data slugs (sabertooth, dire-wolf)."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _keys(source: SourceCreature) -> set[str]:
    return {
        normalize(source.name),
        normalize(source.slug.removeprefix("custom/")),
        *(normalize(a) for a in source.aliases),
    }


def local_candidates(query: str) -> list[SourceCreature]:
    """Exact normalized matches (plus a trailing-s plural fallback) against
    every slug, name, and authored alias. Ambiguity pairs return >1."""
    q = normalize(query)
    if not q:
        return []
    forms = [q]
    if q.endswith("es") and len(q) > 4:
        forms.append(q[:-2])
    if q.endswith("s") and len(q) > 3:
        forms.append(q[:-1])
    for form in forms:
        hits = [s for s in library.sources() if form in _keys(s)]
        if hits:
            return hits
    return []


# -- the gpt-5.1 summon resolver ------------------------------------------------

RESOLVER_SYSTEM = (
    "You are the Summon Resolver for Chimera Creator, a creature-fusion game "
    "played by a 7-year-old. The player typed something into the 'Summon New "
    "Creature' box. Decide what it is. Pick exactly ONE decision:\n"
    "- 'library': the text means one of the library creatures in the index — "
    "a misspelling, nickname, plural, translation, or common synonym. Put the "
    "matching slug(s) in library_slugs (1-3, exactly as written in the index). "
    "If it genuinely could mean two different library creatures, list both.\n"
    "- 'new': a creature NOT in the library — any real animal, extinct "
    "species, mythical beast from any culture, or a fun kid invention like "
    "'axolotl dragon'. Fill in every new-part field.\n"
    "- 'redirect': not a creature at all (an object, a person, a place, "
    "gibberish with no animal in it), or anything gross, gory, violent, "
    "scary-adult, or otherwise wrong for a young child. Write "
    "redirect_message: ONE kind, playful sentence that steers the player back "
    "to animals — never scolding, never naming what was wrong, never "
    "repeating their words. Example tone: 'The summoning circle only answers "
    "to creatures — try a dinosaur, a deep-sea beast, or something legendary!'\n"
    "\n"
    "Rules for 'new' parts — every word must be readable by a 7-year-old: "
    "short, punchy, epic, and NEVER gory, bloody, or scary-adult.\n"
    "- name: Title Case, at most 3 words, pronounceable by a child.\n"
    "- category: 'mythic' (legends, folklore, invented hybrids), 'extinct' "
    "(dinosaurs, ice-age beasts, fossils), or 'living' (real animals today).\n"
    "- blurb: one exciting sentence about the creature.\n"
    "- traits: exactly 3 short powers or features, 2-4 words each, lowercase "
    "(like 'fire breath' or 'super sonar').\n"
    "- contribution: one sentence starting with 'Adds' — what this part gives "
    "a fused chimera.\n"
    "- portrait_description: a complete physical description for a painter — "
    "body plan, colors, textures, signature features, pose. Describe ONLY the "
    "creature's own body: no scenery, no ground, no backdrop, no text.\n"
    "Set unused string fields to '' and unused list fields to []."
)


def _library_index() -> str:
    lines = []
    for s in library.sources():
        alias = f" | also: {', '.join(s.aliases)}" if s.aliases else ""
        lines.append(f"{s.slug} | {s.name}{alias}")
    return "\n".join(lines)


def stub_resolution(query: str) -> SummonResolution:
    """Deterministic keyless-dev/test resolver: everything unknown conjures.
    Mirrors generation.build_stub_record's philosophy — never the product."""
    name = " ".join(w.capitalize() for w in normalize(query).split())[:40] or "Mystery Beast"
    return SummonResolution(
        decision="new",
        library_slugs=[],
        name=name,
        category="living",
        blurb=f"The {name} is a wild wonder nobody has ever fused before!",
        traits=["mystery powers", "wild instincts", "brand-new moves"],
        contribution=f"Adds the untamed spark of the {name.lower()}.",
        portrait_description=(
            f"A majestic {name.lower()}, full body, natural coloring, "
            "detailed fur or scales, dynamic three-quarter pose."
        ),
        redirect_message="",
    )


async def resolve(query: str) -> SummonResolution:
    """gpt-5.1 structured resolver; deterministic stub when AI is disabled."""
    from . import ai

    if not ai.ai_enabled():
        log.info("summon: STUB resolution for %r", query)
        return stub_resolution(query)
    user = (
        f"The player typed: {query!r}\n\n"
        "Library index (slug | name | also answers to):\n"
        f"{_library_index()}"
    )
    return await ai.structured(RESOLVER_SYSTEM, user, SummonResolution, name="summon")


# -- custom-part persistence ----------------------------------------------------

def _file_slug(slug: str) -> str:
    return slug.replace("/", "_")


def to_source(part: CustomPart) -> SourceCreature:
    return SourceCreature(
        slug=part.slug,
        name=part.name,
        category=part.category,
        contribution=part.contribution,
        blurb=part.blurb,
        traits=list(part.traits or []),
        tags=["summoned"],
        art=part.art,
        aliases=list(part.aliases or []),
        custom=True,
    )


def _raw_record(part: CustomPart) -> dict:
    """Shape generation._source_briefs expects, so summoned parts enrich the
    fusion prompt exactly like curated ones."""
    traits = list(part.traits or []) + ["?", "?", "?"]
    return {
        "name": part.name,
        "category": part.category,
        "scale": 5,
        "real_size": "summoned (unknown)",
        "movement_types": [],
        "kid_blurb": part.blurb,
        "contributes": list(part.traits or []),
        "traits": {
            "iconic_appearance": part.portrait_description,
            "signature_weapon": traits[0],
            "movement": traits[1],
            "defense": traits[2],
        },
        "visual_hint": part.portrait_description,
    }


def register(part: CustomPart) -> SourceCreature:
    source = to_source(part)
    library.register_custom(source, _raw_record(part))
    return source


async def load_custom_parts(db: AsyncSession) -> int:
    """Boot: merge every persisted summoned part into the live library."""
    rows = list((await db.execute(select(CustomPart))).scalars())
    for row in rows:
        register(row)
    return len(rows)


def _spawn(coro, label: str) -> asyncio.Task:
    """create_task + loud death (same rationale as api/creatures.spawn)."""
    task = asyncio.create_task(coro)

    def _done(t: asyncio.Task) -> None:
        if not t.cancelled() and t.exception() is not None:
            log.error("background task %s crashed", label, exc_info=t.exception())

    task.add_done_callback(_done)
    return task


async def _portrait_task(part_id: int) -> None:
    """Render the picker portrait, then update the row and the live library.
    Own session — the request that conjured the part is long finished."""
    from ..db import session_factory

    async with session_factory()() as db:
        part = await db.get(CustomPart, part_id)
        if part is None:
            return
        art = await images.generate_part_portrait(
            _file_slug(part.slug), part.name, part.portrait_description
        )
        part.art = art
        part.portrait_status = ImageStatus.complete if art else ImageStatus.failed
        await db.commit()
        library.set_custom_art(part.slug, art)
        if art:
            register(part)  # refresh the registry entry with the final row


# -- the endpoint's brain -------------------------------------------------------

def _respond_local(hits: list[SourceCreature]) -> SummonResponse:
    if len(hits) == 1:
        return SummonResponse(status="matched", source=hits[0])
    return SummonResponse(status="disambiguate", candidates=hits[:3])


async def _conjure(db: AsyncSession, query: str, res: SummonResolution) -> SummonResponse:
    from . import ai

    slug = f"custom/{_slugify(res.name)}"

    # The resolver invented something we already have (curated or summoned a
    # different way) — that is a match, never a duplicate.
    existing = library.source_by_slug(slug) or library.source_by_slug(_slugify(res.name))
    if existing:
        return SummonResponse(status="matched", source=existing)
    row = (await db.execute(select(CustomPart).where(CustomPart.slug == slug))).scalar_one_or_none()
    if row is not None:
        return SummonResponse(status="matched", source=register(row))

    part = CustomPart(
        slug=slug,
        name=res.name,
        category=res.category,
        blurb=res.blurb,
        contribution=res.contribution or f"Adds the powers of the {res.name.lower()}.",
        traits=res.traits[:3],
        aliases=sorted({normalize(query)} - {normalize(res.name)}),
        portrait_description=res.portrait_description,
        portrait_status=ImageStatus.pending if ai.ai_enabled() else ImageStatus.failed,
    )
    db.add(part)
    await db.flush()
    source = register(part)

    if ai.ai_enabled():
        _spawn(_portrait_task(part.id), f"summon-portrait:{part.slug}")
        portrait_status = "rendering"
    else:
        portrait_status = "failed"  # stub mode: no key, no render — never the product
    log.info("summon: conjured %s (%s) from %r", part.slug, part.category, query)
    return SummonResponse(status="conjured", source=source, portrait_status=portrait_status)


async def summon(db: AsyncSession, query: str) -> SummonResponse:
    query = query.strip()

    # 1. Local: slugs, names, and the authored aliases — no AI call.
    hits = local_candidates(query)
    if hits:
        return _respond_local(hits)

    # 2. The resolver decides: library / new / redirect.
    res = await resolve(query)

    if res.decision == "library":
        known = [s for slug in dict.fromkeys(res.library_slugs)
                 if (s := library.source_by_slug(slug))]
        if len(known) >= 1:
            return _respond_local(known)
        # Resolver pointed at slugs we do not have — fall through.

    if res.decision == "new" and res.name.strip():
        return await _conjure(db, query, res)

    return SummonResponse(status="redirect",
                          message=res.redirect_message.strip() or REDIRECT_FALLBACK)
