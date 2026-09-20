"""Hero-image pipeline (docs/AI_CONTRACTS.md §1B, §3).

gpt-image-2.5 Flare with `background=transparent` (ai.IMAGE_MODEL; the
2026-09-20 bakeoff moved it off gpt-image-1.5) — native alpha, which matters
for translucent flame/lightning/spray edges that a chroma key destroys.
OpenAI-only by decision; on repeated failure we mark the row `failed` and the
UI offers a friendly retry ("the lab is recharging").

Files land in the backend-owned media dir (served at /media by the API, so
prod does not depend on writing into the frontend image). A creature row is
created with image_status=pending; the text record is already saved, so
nothing here may ever lose a creature.
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
from pathlib import Path

from ..config import get_settings
from ..models import Creature
from ..schemas import Strict

log = logging.getLogger("chimera.images")

HERO_SIZE = "1536x1024"
KEYART_SIZE = "1536x1024"
THUMB_PX = 512

# gpt-image-1.5 only ever hands back PNG, and a transparent 1536x1024 hero is
# ~2.5MB of it — nine of those is a Codex page. Every render is transcoded to
# WebP on its way to disk: q90 measures ~90% smaller on this art with alpha
# intact and no visible difference at 1:1. This is a permanent step in the
# save path, not a one-time migration — new creatures land as WebP too.
MEDIA_EXT = ".webp"
WEBP_QUALITY = 90
WEBP_METHOD = 6  # slowest/best encoder pass; a few hundred ms, paid once


def to_webp(png: bytes) -> bytes:
    """PNG bytes -> WebP bytes, keeping alpha exactly when the source has it.

    Hero cutouts are RGBA and must stay that way; opaque key art is written as
    RGB so it does not carry a pointless all-255 alpha plane.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(png))
    has_alpha = img.mode in ("RGBA", "LA") or "transparency" in img.info
    img = img.convert("RGBA" if has_alpha else "RGB")
    out = io.BytesIO()
    img.save(out, "WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
    return out.getvalue()


# Part portraits (the 160 pregenerated picker portraits AND every summoned
# one) are stored TIGHT: trimmed to the creature's own alpha bounding box, any
# aspect ratio, no baked-in canvas or margin. Square canvases centred each
# creature at whatever height its silhouette happened to land, so a rail of
# them read as a row of creatures floating at different heights, some kissing
# the card edge. With a tight image every UI context anchors the creature
# itself — cards sit it on a shared ground line (object-fit: contain,
# object-position bottom), orbit circles centre it — and the spacing is the
# CSS's decision, the same for every part. scripts/normalize_portraits.py
# applies this to the committed library; generate_part_portrait applies it to
# every new render; the boot pass in services/summon.py catches portraits
# already on the media volume.
#
# 512, not 1024 (2026-09-20): the biggest box a part portrait ever fills is
# the 168px summon candidate card — 336 device px on the iPad — so a 1024px
# file was 4x the pixels Safari would ever paint. The old 160-file library
# was 42MB / ~3.7MB decoded per portrait; at 512 it is a quarter of both, and
# the picker rail stops re-decoding a hundred oversized bitmaps on scroll.
# Bump summon.TIGHT_MARKER whenever this changes so the boot pass re-cuts the
# portraits already on the volume.
PORTRAIT_MAX_PX = 512
#: Portraits are painted at a third of their pixel size at most; q85 is
#: indistinguishable from q90 there and a third smaller on the wire.
PORTRAIT_WEBP_QUALITY = 85
#: Alpha below this is fringe (resampling haze, faint glow tails), not creature.
PORTRAIT_ALPHA_THRESH = 8


def normalize_portrait(data: bytes, *, fmt: str = "WEBP") -> bytes:
    """Trim to the alpha bounding box and cap the long side at PORTRAIT_MAX_PX.

    Accepts PNG or WebP bytes; returns `fmt` ("WEBP" or "PNG") with alpha
    intact. Idempotent: a tight portrait comes back unchanged in shape.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGBA")
    mask = img.getchannel("A").point(lambda a: 255 if a > PORTRAIT_ALPHA_THRESH else 0)
    bbox = mask.getbbox()
    if bbox:
        img = img.crop(bbox)
    side = max(img.size)
    if side > PORTRAIT_MAX_PX:
        scale = PORTRAIT_MAX_PX / side
        img = img.resize(
            (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
            Image.LANCZOS,
        )
    out = io.BytesIO()
    if fmt.upper() == "PNG":
        img.save(out, "PNG", optimize=True)
    else:
        img.save(out, "WEBP", quality=PORTRAIT_WEBP_QUALITY, method=WEBP_METHOD)
    return out.getvalue()


def find_media(directory: Path, stem: str) -> Path | None:
    """The saved file for `stem`, WebP first, then PNG.

    Art generated before the WebP switch is still on disk as .png and still
    perfectly good; nothing is rewritten just to change its extension, so
    every read goes through here.
    """
    for ext in (MEDIA_EXT, ".png"):
        path = directory / f"{stem}{ext}"
        if path.exists():
            return path
    return None

HERO_STYLE = (
    "Epic realistic fantasy creature concept art for a AAA video game. "
    "Cinematic dramatic lighting, hyper-detailed textures, museum-quality "
    "creature design. The creature is ONE coherent invented species. Full "
    "body visible, dynamic three-quarter hero pose, not touching the image "
    "edges. Fierce and epic but suitable for a 7-year-old: no gore, no "
    "blood. Absolutely no text, letters, numbers, logos, or watermarks. "
    "Transparent background — the isolated creature ONLY: no scenery, no "
    "terrain base, no backdrop or environment, even if the description "
    "mentions surroundings (at most a soft contact shadow under its feet). "
    "Creature description: "
)


# Summoned-part portraits must sit in the same visual family as the 160
# pregenerated picker portraits. Style + isolation language is copied VERBATIM
# from the pregen pipeline (scripts/assetlib.py PORTRAIT_STYLE and
# scripts/generate_assets.py PORTRAIT_ISOLATION) — keep the three in sync.
PART_PORTRAIT_STYLE = (
    "Realistic AAA creature portrait for a neon sci-fi game, aimed at kids "
    "7-10. The creature keeps its NATURAL realistic coloring and detailed "
    "texture, lit dramatically with a subtle electric-cyan and violet rim "
    "light as if standing in a dark holographic lab. Epic, fierce, premium — "
    "never gory. Full body visible, three-quarter dramatic pose, centered, "
    "not touching image edges. Absolutely no text or watermarks. "
)
PART_PORTRAIT_ISOLATION = (
    " CRITICAL: this is a cut-out sprite of the creature ALONE. Do not paint "
    "any scenery, environment, habitat, ground, floor, terrain, rock, water, "
    "waves, snow, lava, sand, clouds, sky, mist, smoke, dust, moon, or cast "
    "shadow. No base, no platform, no pedestal, no rectangular backdrop panel, "
    "no vignette. Everything that is not the creature's own body must be "
    "completely empty and fully transparent, right up to its silhouette. "
    "Effects like fire or lightning are allowed only where they touch the "
    "creature's own body. Transparent background."
)
PART_SIZE = "1024x1024"


def _media_dir():
    d = get_settings().media_dir / "creatures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parts_dir():
    d = get_settings().media_dir / "parts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def part_portrait_prompt(name: str, description: str) -> str:
    """Exactly the pregen part-portrait prompt shape (generate_assets.py)."""
    return (PART_PORTRAIT_STYLE + "Creature: " + name + ". " +
            description.rstrip(".") + "." + PART_PORTRAIT_ISOLATION)


def part_portrait_prompt_anonymous(description: str) -> str:
    """The same style + isolation shell with NO 'Creature: <name>.' clause.

    Used after the safety filter rejects the named prompt: the trademarked
    name is what trips it, so the second try is anatomy only."""
    return (PART_PORTRAIT_STYLE + description.strip().rstrip(".") + "." +
            PART_PORTRAIT_ISOLATION)


# -- the safety-filter fallback -------------------------------------------------
# gpt-image-1.5 rejects prompts that name famous trademarked characters
# (Charizard, Mewtwo, Night Fury...): a 400 with code=moderation_blocked and
# "Your request was rejected by the safety system". The filter keys on the NAME
# and franchise words, not the anatomy — "Leafeon" failed every attempt while
# the resolver's "Leaf Fox" rendered first time. So a rejected prompt is never
# re-sent; the remaining attempts go out with the names and brands scrubbed.

SAFETY_CODES = frozenset({"moderation_blocked", "content_policy_violation"})
SAFETY_PHRASES = (
    "rejected by the safety system",
    "safety system",
    "moderation_blocked",
    "content_policy_violation",
)


def is_safety_rejection(exc: BaseException) -> bool:
    """True when the image API refused the PROMPT (as opposed to failing).

    Robust to SDK shape: openai.BadRequestError carries `.code` and `.body`,
    but a plain Exception whose text is the prod message counts too."""
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code in SAFETY_CODES:
        return True
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        if isinstance(err, dict) and err.get("code") in SAFETY_CODES:
            return True
    text = str(exc).lower()
    return any(phrase in text for phrase in SAFETY_PHRASES)


#: Franchise / brand / company tokens the image filter is touchy about. Modest
#: on purpose: the character NAMES come from the caller; these are the words
#: a description uses to point at them ("a Pokémon-like fire lizard").
FRANCHISE_WORDS = (
    "pokémon", "pokemon", "nintendo", "disney", "pixar", "dreamworks", "marvel",
    "dc comics", "star wars", "harry potter", "hogwarts", "how to train your dragon",
    "minecraft", "roblox", "godzilla", "king kong", "digimon", "yu-gi-oh", "mario",
    "zelda", "fortnite", "pikachu",
)

# Regex building blocks. Names match word-bounded, case-insensitive, with any
# mix of spaces / hyphens / apostrophes between their tokens ("Night Fury",
# "Night-Fury", "NightFury") and an optional possessive.
_SEP = r"[\s\-‐‑–'’]*"
_POSS = r"(?:['’]s)?"
_STYLE = r"(?:style|like|inspired|type|esque|themed|ish)"
_ARTICLE = r"(?:(?:a|an|the|this|that|its|his|her|your)\s+)?"
_QUALIFIER = r"(?:(?:famous|iconic|classic|popular|legendary|well-known|beloved)\s+)?"
_COMPARISON = (
    r"(?:just\s+like|like|unlike|resembling|resembles|similar\s+to|inspired\s+by|"
    r"reminiscent\s+of|in\s+the\s+style\s+of|modeled\s+after|modelled\s+after|"
    r"based\s+on|straight\s+out\s+of|out\s+of|from|of|as\s+in|a\s+la|à\s+la)"
)
#: "...from the Godzilla movies" — the trailing noun goes with the brand.
_WORLD = (
    r"(?:\s+(?:world|universe|franchise|games?|series|movies?|films?|cartoons?|shows?|"
    r"anime))?"
)
#: After name replacement: "like a the creature" is a fragment, not a comparison.
_STALE_COMPARISON = (
    r"(?:just\s+like|like|unlike|resembling|resembles|similar\s+to|inspired\s+by|"
    r"reminiscent\s+of|in\s+the\s+style\s+of|modeled\s+after|modelled\s+after|based\s+on)"
)


def _sub(pattern: str, repl, text: str) -> str:
    """Case-insensitive re.sub (every scrub rule is)."""
    return re.sub("(?i)" + pattern, repl, text)


def _phrase(text: str) -> str | None:
    """A name/brand as a regex core, or None when too short to be safe."""
    tokens = re.findall(r"[^\W_]+", text)
    if not tokens or sum(map(len, tokens)) < 3:
        return None
    return _SEP.join(re.escape(t) for t in tokens)


def _the_creature(m: re.Match) -> str:
    poss = "'s" if m.group("poss") else ""
    before = m.string[:m.start()].rstrip()
    word = "The creature" if not before or before[-1] in ".!?" else "the creature"
    return word + poss


def _tidy(text: str) -> str:
    """Collapse the holes the scrub leaves: doubled punctuation, empty parens,
    dangling articles and connectives, runs of whitespace."""
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)
    text = _sub(r"\b(?:a|an|the|this|that)\s+(the creature)\b", r"\1", text)
    text = _sub(r"\b(?:the creature)(?:['’]s)?[\s\-]*" + _STYLE + r"\b", "the creature", text)
    text = _sub(r",?\s*\b" + _STALE_COMPARISON + r"\s+" + _ARTICLE + r"the creature(?:['’]s)?\b",
                "", text)
    for _ in range(2):
        text = re.sub(r"\s+([,.;:!?)])", r"\1", text)
        text = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", text)
        text = re.sub(r"\.(?:\s*\.)+", ".", text)
        text = _sub(r"\b(?:a|an|the|with|of|from|like|and|or|but)\s*(?=[,.;:!?)]|$)", "", text)
        text = _sub(r"\b(?:a|an|the)\s+(of|with|from|in|on|and|or|but)\b", r"\1", text)
    text = re.sub(r"^\s*[,.;:]+\s*", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    # Sentence starts that a removal exposed.
    text = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
    return text


def debrand(text: str, names: list[str]) -> str:
    """Regex scrub: franchise words gone, every given name -> "the creature".

    "<Name>-style" / "like a <Name>" / "from the <Brand> movies" fragments
    are dropped whole (a painter who has never seen the character gets
    nothing from them); a bare name becomes "the creature" with its
    possessive kept ("Charizard's tail" -> "the creature's tail"). Anatomy
    words are never touched. Brands go first so a name inside a franchise
    title ("How to Train Your Dragon") cannot break the title apart."""
    if not text:
        return text
    # A brand that is also the part's own name (Godzilla, Pikachu) is the
    # subject of the description: the name pass keeps it as "the creature".
    name_keys = {" ".join(re.findall(r"[^\W_]+", n.lower())) for n in names if n}
    for word in sorted(FRANCHISE_WORDS, key=len, reverse=True):
        core = _phrase(word)
        if not core or " ".join(re.findall(r"[^\W_]+", word)) in name_keys:
            continue
        # "Pokémon-like" is an adjective: drop it, keep the article for the noun.
        text = _sub(rf"\b{core}{_POSS}{_SEP}{_STYLE}\b", "", text)
        text = _sub(rf",?\s*\b{_COMPARISON}\s+{_ARTICLE}{_QUALIFIER}{core}{_POSS}{_WORLD}\b",
                    "", text)
        text = _sub(rf"\b{_ARTICLE}{_QUALIFIER}{core}{_POSS}{_WORLD}\b", "", text)
    phrases = []
    for name in sorted({n.strip() for n in names if n and n.strip()}, key=len, reverse=True):
        core = _phrase(name)
        if core and name.strip().lower() not in ("the creature", "creature"):
            phrases.append(core)
    for core in phrases:
        text = _sub(rf"\b{core}{_POSS}{_SEP}{_STYLE}\b", "", text)
        text = _sub(rf",?\s*\b{_COMPARISON}\s+{_ARTICLE}{_QUALIFIER}{core}{_POSS}{_WORLD}\b",
                    "", text)
        text = _sub(rf"\b{_ARTICLE}{_QUALIFIER}{core}(?P<poss>{_POSS})\b", _the_creature, text)
    return _tidy(text)


class DebrandedDescription(Strict):
    """gpt-5.1 structured-output contract for the rewrite."""

    description: str


DEBRAND_SYSTEM = (
    "Rewrite this creature description for a painter who has never seen any "
    "video game, cartoon, movie, book, or toy franchise. Keep EVERY physical "
    "detail — body plan, colors, textures, signature features, pose, size "
    "cues — but remove every character name, franchise / brand / company "
    "name, and any 'like <character>' or '<character>-style' comparison. "
    "Never mention that anything was removed or that the creature comes "
    "from anywhere. Output plain anatomy only, in about the same length, as "
    "one flowing description a painter could work from directly."
)


async def debrand_via_llm(text: str, names: list[str]) -> str:
    """One gpt-5.1 rewrite to plain anatomy, then the regex scrub on top
    (belt and braces). Any failure falls back to the regex scrub alone."""
    from . import ai

    wanted = [n for n in dict.fromkeys(n.strip() for n in names) if n]
    out = text
    try:
        if not ai.ai_enabled():
            raise RuntimeError("AI disabled")
        user = (
            "Names that must not appear in any form (nor anything that hints "
            f"at them): {', '.join(wanted) or '(none given)'}\n\n"
            f"Description:\n{text}"
        )
        res = await ai.structured(DEBRAND_SYSTEM, user, DebrandedDescription, name="debrand")
        out = res.description.strip() or text
    except Exception as exc:  # noqa: BLE001 - the regex scrub is the floor
        log.warning("images: LLM debrand failed (%s) — regex scrub only", str(exc)[:200])
    return debrand(out, wanted)


# Two redesign distances. "close" threads the needle (Nick, 2026-09-20): the
# player asked for THIS creature, so it should still read as a cousin of it.
# "far" is the last resort when even the cousin is refused.
REIMAGINE_CLOSE_SYSTEM = (
    "The image model refused a faithful portrait of this creature because "
    "its anatomy alone identifies a famous copyrighted character. Describe "
    "a CLOSE COUSIN of it for a kids' creature game: keep the same body "
    "plan, the same element and powers, the same overall palette family, "
    "size, mood and pose — a child who asked for this creature should still "
    "recognize the kind of beast they wanted. Change ONLY the two or three "
    "signature details that make it that specific character: shift its "
    "exact colors by a shade or two, alter a marking, a crest, a tail tip, "
    "a proportion. Never name or hint at the original. Output plain anatomy "
    "only — body plan, colors, textures, features, pose — as one flowing "
    "description a painter could work from directly, about the same length "
    "as the input."
)
REIMAGINE_FAR_SYSTEM = (
    "The image model refused a portrait of this creature twice because its "
    "anatomy identifies a famous copyrighted character. Reimagine it as an "
    "ORIGINAL species for a kids' creature game: keep the general animal "
    "type, size, mood and one or two of its powers, but change the color "
    "scheme, the silhouette and the signature features enough that nobody "
    "could mistake it for any existing character. Never name or hint at the "
    "original. Output plain anatomy only — body plan, colors, textures, "
    "features, pose — as one flowing description a painter could work from "
    "directly, about the same length as the input."
)


async def reimagine_via_llm(text: str, names: list[str], *, distance: str = "close") -> str:
    """Rungs three and four: not a scrub but a redesign (the 2026-09-20
    resweep showed Charizard, Mewtwo, Blastoise and Umbreon refused even with
    every name gone — the filter knows them by shape). `distance` is "close"
    (a cousin the player still recognizes) or "far" (a clearly new species).
    The regex scrub runs on top; if the model call fails the caller gets a
    clearly-different text back and the ladder ends on the next refusal."""
    from . import ai

    wanted = [n for n in dict.fromkeys(n.strip() for n in names) if n]
    system = REIMAGINE_FAR_SYSTEM if distance == "far" else REIMAGINE_CLOSE_SYSTEM
    out = ("A close cousin of, but not quite: " if distance != "far"
           else "An original creature loosely inspired by, but clearly different from: ") + text
    try:
        if not ai.ai_enabled():
            raise RuntimeError("AI disabled")
        user = (
            "Names that must not appear in any form (nor anything that hints "
            f"at them): {', '.join(wanted) or '(none given)'}\n\n"
            f"Refused description:\n{text}"
        )
        res = await ai.structured(system, user, DebrandedDescription, name="reimagine")
        out = res.description.strip() or out
    except Exception as exc:  # noqa: BLE001 - late rungs: degrade, never crash
        log.warning("images: LLM reimagine (%s) failed (%s) — using the scrubbed text",
                    distance, str(exc)[:200])
    return debrand(out, wanted)


#: Prompt variants a refused render walks through, in order. "named" is the
#: pregen-shaped prompt, "anonymous" the faithful name-free rewrite, "cousin"
#: a close redesign the player still recognizes, "distinct" a clearly new
#: species — the last resort.
_NEXT_VARIANT = {"named": "anonymous", "anonymous": "cousin", "cousin": "distinct"}


async def _rewrite_for(variant: str, text: str, names: list[str]) -> str:
    if variant == "anonymous":
        return await debrand_via_llm(text, names)
    return await reimagine_via_llm(text, names, distance="close" if variant == "cousin" else "far")


async def _backoff(attempt: int) -> None:
    """Retry pause for transient API failures (tests stub this out)."""
    await asyncio.sleep(2 * attempt)


#: Four rungs: named, anonymous, cousin, distinct (refused renders are free;
#: only the text rewrites cost, a few tenths of a cent each).
PART_PORTRAIT_ATTEMPTS = 4


async def generate_part_portrait(
    file_slug: str, name: str, description: str, *, names: list[str] | None = None
) -> str | None:
    """Render a summoned part's picker portrait; return its web path or None.

    quality=medium (~26s, the verified fast path) — a picker card, not a hero
    render. Attempt 1 is the pregen-shaped prompt (with "Creature: <name>.");
    a safety rejection switches the remaining attempts to an anonymous prompt
    (name and franchise words scrubbed, anatomy kept). A rejected prompt is
    never re-sent; transient errors retry with backoff. Three attempts total,
    then None; the caller marks the row failed. `names` are extra names to
    scrub from the description (the part's own name always is).
    """
    from . import ai

    if not ai.ai_enabled():
        log.info("images: AI disabled — no portrait for part %s", file_slug)
        return None

    prompt = part_portrait_prompt(name, description)
    variant = "named"
    rejected: set[str] = set()
    for attempt in range(1, PART_PORTRAIT_ATTEMPTS + 1):
        try:
            png = await _render(prompt, quality="medium", size=PART_SIZE)
        except Exception as exc:  # noqa: BLE001 - API errors: log and retry
            if not is_safety_rejection(exc):
                log.warning("images: part portrait attempt %d (%s) failed for %s: %s",
                            attempt, variant, file_slug, str(exc)[:200])
                await _backoff(attempt)
                continue
            rejected.add(prompt)
            nxt = _NEXT_VARIANT.get(variant)
            if nxt is None:
                log.warning("images: part portrait attempt %d for %s: every prompt variant "
                            "was safety-rejected — giving up", attempt, file_slug)
                break
            log.warning("images: part portrait attempt %d for %s (%s) safety-rejected (%s) "
                        "— trying the %s prompt", attempt, file_slug, variant,
                        str(exc)[:120], nxt)
            text = await _rewrite_for(nxt, description, [name, *(names or [])])
            prompt, variant = part_portrait_prompt_anonymous(text), nxt
            if prompt in rejected:
                break
            continue
        tight = await asyncio.to_thread(normalize_portrait, png)
        path = _parts_dir() / f"{file_slug}{MEDIA_EXT}"
        path.write_bytes(tight)
        log.info("images: part portrait %s landed (%s prompt, attempt %d, %dKB webp "
                 "from %dKB png)", file_slug, variant, attempt,
                 len(tight) // 1024, len(png) // 1024)
        return f"/media/parts/{file_slug}{MEDIA_EXT}"
    return None


def hero_prompt(record_like) -> str:
    """The one true hero prompt. Used by the runtime render path AND the seed
    pipeline (scripts/gen_seed_creatures.py) so pregenerated art is guaranteed
    to match runtime art. `record_like` needs `.visual_spec` and `.name`."""
    return HERO_STYLE + (record_like.visual_spec or record_like.name)


async def _render(prompt: str, *, quality: str, size: str = HERO_SIZE) -> bytes:
    from . import ai

    resp = await ai.client().images.generate(
        model=ai.IMAGE_MODEL, prompt=prompt, size=size, quality=quality,
        background="transparent", output_format="png",
    )
    return base64.b64decode(resp.data[0].b64_json)


def _hero_names(creature) -> list[str]:
    """The names a visual_spec might lean on that the safety filter can object
    to: the SUMMONED source parts' display names (a "Night Fury" or "Charizard"
    is the usual culprit) plus the creature's own name. Curated parts are plain
    animals — "shark", "dragon" — and never trip the filter; scrubbing them
    would strip real anatomy from the prompt, so they are deliberately left
    alone. `creature` may be a SimpleNamespace without `sources`."""
    from . import library

    names = [
        library.display_name(s)
        for s in (getattr(creature, "sources", None) or [])
        if str(s).startswith("custom/")
    ]
    own = getattr(creature, "name", "") or ""
    if own:
        names.append(own)
    return names


def hero_ladder() -> tuple[str, str, str, str]:
    """(hero_quality, hero_quality, "medium", "medium") — four rungs so the
    safety ladder (named, anonymous, cousin, distinct) fits. The cost knob
    lives in config.Settings (CHIMERA_HERO_QUALITY), read at call time so a
    dashboard change takes effect on the next render, and tests can flip it."""
    quality = get_settings().hero_quality
    return (quality, quality, "medium", "medium")


async def generate_hero(creature: Creature) -> str | None:
    """Render the transparent hero PNG; return its web path or None.

    Attempts: high → high (retry) → medium (verified fast path), the first
    two at Settings.hero_quality. A safety rejection (the visual_spec named a
    trademarked character) rewrites the spec once to plain anatomy and
    continues the ladder with that prompt — a rejected prompt is never
    re-sent. None only after the ladder is spent; caller sets
    image_status=failed.
    """
    from . import ai

    if not ai.ai_enabled():
        log.info("images: AI disabled — no hero for creature %s", creature.id)
        return None

    prompt = hero_prompt(creature)
    variant = "named"
    rejected: set[str] = set()
    for attempt, quality in enumerate(hero_ladder(), 1):
        try:
            png = await _render(prompt, quality=quality)
        except Exception as exc:  # noqa: BLE001 - API errors: log and retry
            if not is_safety_rejection(exc):
                log.warning("images: hero attempt %d (%s, %s) failed for %s: %s",
                            attempt, quality, variant, creature.id, str(exc)[:200])
                await _backoff(attempt)
                continue
            rejected.add(prompt)
            nxt = _NEXT_VARIANT.get(variant)
            if nxt is None:
                log.warning("images: hero attempt %d (%s) for %s: every prompt variant was "
                            "safety-rejected — giving up", attempt, quality, creature.id)
                break
            log.warning("images: hero attempt %d (%s) for %s (%s) safety-rejected (%s) — "
                        "trying the %s visual_spec", attempt, quality, creature.id, variant,
                        str(exc)[:120], nxt)
            spec = await _rewrite_for(nxt, creature.visual_spec or creature.name,
                                      _hero_names(creature))
            prompt, variant = HERO_STYLE + spec, nxt
            if prompt in rejected:
                break
            continue
        webp = await asyncio.to_thread(to_webp, png)
        path = _media_dir() / f"{creature.id}{MEDIA_EXT}"
        path.write_bytes(webp)
        log.info("images: hero for %s (%s, %s prompt, attempt %d, %dKB webp from %dKB png)",
                 creature.id, quality, variant, attempt, len(webp) // 1024, len(png) // 1024)
        return f"/media/creatures/{creature.id}{MEDIA_EXT}"
    return None


def _thumb_from_hero_bytes(hero_bytes: bytes) -> bytes:
    """Alpha-aware square FIT: the whole creature, never a crop.

    A square crop chopped wide creatures (wings, serpent coils) at the card
    edge. Instead: tight alpha bbox, then letterbox onto a transparent square
    with a small margin so every silhouette reads complete in the Codex.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(hero_bytes)).convert("RGBA")
    bbox = img.getchannel("A").point(lambda a: 255 if a > 20 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    side = max(img.width, img.height)
    margin = max(2, side // 25)
    canvas = Image.new("RGBA", (side + 2 * margin,) * 2, (0, 0, 0, 0))
    canvas.paste(img, ((canvas.width - img.width) // 2, (canvas.height - img.height) // 2))
    canvas = canvas.resize((THUMB_PX, THUMB_PX), Image.LANCZOS)
    out = io.BytesIO()
    canvas.save(out, "WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
    return out.getvalue()


async def generate_thumb(creature: Creature) -> str | None:
    """Derive the codex thumbnail from the saved hero. Local, instant."""
    hero = find_media(_media_dir(), str(creature.id))
    if hero is None:
        return None
    thumb = _media_dir() / f"{creature.id}_thumb{MEDIA_EXT}"
    thumb.write_bytes(await asyncio.to_thread(_thumb_from_hero_bytes, hero.read_bytes()))
    return f"/media/creatures/{creature.id}_thumb{MEDIA_EXT}"


async def generate_championship_art(fa: Creature, fb: Creature) -> str | None:
    """Finals key art via images.edit with both hero cutouts (bakeoff-validated
    for two-creature identity preservation).

    Generated when the FINALISTS are known (semifinals complete), before the
    winner is — so the scene is a neutral titanic clash, and the ~74s render
    hides inside the final prediction + battle. Championship only, never
    blocking: None simply means the ceremony uses the composited finale.
    """
    from . import ai

    if not ai.ai_enabled():
        return None
    # Deterministic battles make repeat finalist pairs common (same favorite
    # eight, same bracket) — the art depends only on the pair, so a previous
    # render is this render.
    lo, hi = sorted((fa.id, fb.id))
    existing = find_media(_media_dir(), f"final_{lo}_{hi}")
    if existing is not None:
        return f"/media/creatures/{existing.name}"
    a = find_media(_media_dir(), str(fa.id))
    b = find_media(_media_dir(), str(fb.id))
    if a is None or b is None:
        return None
    mime = {".webp": "image/webp", ".png": "image/png"}

    prompt = (
        "Epic cinematic championship key art for a AAA monster game, child-"
        "friendly (no gore, no blood). The FIRST attached creature and the "
        "SECOND attached creature clash mid-battle in a futuristic holographic "
        "grand arena at night — gold championship light beams, violet and "
        "cyan energy, sparks and spray flying, both titans rearing at each "
        "other in a perfectly balanced duel, neither winning. Keep BOTH "
        "creatures' designs EXACTLY as shown in the attached images — same "
        "anatomy, colors, plates, proportions. No text or watermarks."
    )
    try:
        resp = await ai.client().images.edit(
            model=ai.IMAGE_MODEL,
            image=[(a.name, io.BytesIO(a.read_bytes()), mime[a.suffix]),
                   (b.name, io.BytesIO(b.read_bytes()), mime[b.suffix])],
            prompt=prompt, size=KEYART_SIZE, quality=get_settings().keyart_quality,
            output_format="png",
        )
        png = base64.b64decode(resp.data[0].b64_json)
        webp = await asyncio.to_thread(to_webp, png)
        path = _media_dir() / f"final_{lo}_{hi}{MEDIA_EXT}"
        path.write_bytes(webp)
        return f"/media/creatures/final_{lo}_{hi}{MEDIA_EXT}"
    except Exception as exc:  # noqa: BLE001 - ceremony must never block
        log.warning("images: championship art failed (%s vs %s): %s",
                    fa.id, fb.id, str(exc)[:200])
        return None
