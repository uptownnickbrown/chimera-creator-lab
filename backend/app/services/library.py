"""Source-creature and environment library, loaded from committed JSON.

`data/source_creatures.json` and `data/environments.json` are authored content
(spec §22). They may not exist yet — the app must boot, serve an empty library,
and log one line rather than crash (ARCHITECTURE.md: a missing input never
takes a screen down).

Accepted shapes for each file: a bare list of records, or {"sources": [...]} /
{"environments": [...]} / {"items": [...]}.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ..config import get_settings
from ..schemas import ENVIRONMENT_SLUGS, Environment, SourceCreature

log = logging.getLogger("chimera.library")

_sources: list[SourceCreature] = []
_environments: list[Environment] = []
_raw_sources: dict[str, dict] = {}
_raw_environments: dict[str, dict] = {}
_loaded = False

# Summoned parts (custom_parts table) mirrored in memory so every consumer —
# /api/library, validate_slugs, prompt enrichment — sees one merged library.
# Single-player, single-process: the same pattern as generation.PROGRESS.
_customs: list[SourceCreature] = []
_raw_customs: dict[str, dict] = {}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _read_json_list(path: Path, *keys: str) -> list[dict]:
    if not path.exists():
        log.info("library: %s not present — serving an empty library for now", path.name)
        return []
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("library: %s could not be read (%s) — skipping", path.name, exc)
        return []
    if isinstance(raw, dict):
        for key in (*keys, "items"):
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break
        else:
            log.warning("library: %s has no list under %s — skipping", path.name, keys)
            return []
    if not isinstance(raw, list):
        log.warning("library: %s is not a list — skipping", path.name)
        return []
    return [r for r in raw if isinstance(r, dict)]


def _strings(value: object) -> list[str]:
    """Flatten the several shapes authors use for trait lists."""
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, (str, int, float))]
    return []


def _coerce_source(rec: dict) -> SourceCreature | None:
    name = rec.get("name") or rec.get("title") or rec.get("slug")
    if not name:
        return None
    slug = rec.get("slug") or rec.get("id") or _slugify(str(name))

    # `contributes` is the "what this part adds" list the Fusion Lab shows.
    contributes = _strings(rec.get("contributes") or rec.get("adds"))
    contribution = str(rec.get("contribution") or "")
    if not contribution and contributes:
        contribution = "Adds " + ", ".join(contributes) + "."

    # `emoji_fallback` in the data file is deliberately ignored: no emoji as UI
    # iconography (ARCHITECTURE.md). The <Asset> slot plate is the fallback.
    return SourceCreature(
        slug=str(slug),
        name=str(name),
        category=str(rec.get("category") or rec.get("kind") or "living"),
        contribution=contribution,
        blurb=str(rec.get("kid_blurb") or rec.get("blurb") or rec.get("description") or ""),
        traits=contributes or _strings(rec.get("traits") or rec.get("child_traits")),
        tags=_strings(rec.get("tags")),
        art=rec.get("art") or rec.get("image") or None,
        aliases=_strings(rec.get("aliases")),
    )


def _coerce_environment(rec: dict) -> Environment | None:
    name = rec.get("name") or rec.get("title") or rec.get("slug")
    if not name:
        return None
    # Environment slugs are normalized to the underscore form, because they are
    # also the keys of CreatureRecord.environment_affinities. An arena the
    # affinity map cannot be indexed by would silently flatten every battle.
    slug = str(rec.get("slug") or rec.get("id") or _slugify(str(name))).replace("-", "_")
    if slug not in ENVIRONMENT_SLUGS:
        log.warning("library: environment %r is not one of the nine schema arenas", slug)

    blurb = str(rec.get("blurb") or rec.get("description") or "")
    if not blurb:
        labels = [
            str(p.get("label"))
            for p in rec.get("kid_properties") or []
            if isinstance(p, dict) and p.get("label")
        ]
        blurb = " · ".join(labels)

    return Environment(
        slug=slug,
        name=str(name),
        blurb=blurb,
        art=rec.get("art") or rec.get("image") or None,
    )


def load_library(data_dir: Path | None = None) -> None:
    """Read the data files into memory. Called once at startup; idempotent.

    Also resets the customs registry — the caller (lifespan / test fixture)
    re-registers DB-backed custom parts afterwards via register_custom().
    """
    global _sources, _environments, _raw_sources, _raw_environments, _loaded
    global _customs, _raw_customs
    _customs = []
    _raw_customs = {}
    data_dir = data_dir or get_settings().data_dir

    src_records = _read_json_list(data_dir / "source_creatures.json", "sources", "creatures")
    env_records = _read_json_list(data_dir / "environments.json", "environments")

    _sources = [s for s in (_coerce_source(r) for r in src_records) if s]
    _environments = [e for e in (_coerce_environment(r) for r in env_records) if e]
    # Raw records keep the full authored detail (traits dict, scale, sim
    # block, advantages_hint...) for AI prompt enrichment; keys are the
    # normalized slugs the coerced objects carry.
    _raw_sources = {
        s.slug: r for s, r in zip((_coerce_source(r) for r in src_records), src_records) if s
    }
    _raw_environments = {
        e.slug: r for e, r in zip((_coerce_environment(r) for r in env_records), env_records) if e
    }
    _loaded = bool(_sources or _environments)

    if _loaded:
        log.info("library: %d sources, %d environments", len(_sources), len(_environments))
    else:
        log.info("library: empty (data files not authored yet) — the API still serves)")


def sources() -> list[SourceCreature]:
    """Curated parts + Henry's summoned parts, one merged picker library."""
    return list(_sources) + list(_customs)


def register_custom(source: SourceCreature, raw: dict) -> None:
    """Merge one summoned part into the live library (new or updated)."""
    global _customs
    _customs = [c for c in _customs if c.slug != source.slug] + [source]
    _raw_customs[source.slug] = raw


def set_custom_art(slug: str, art: str | None) -> None:
    """The portrait render landed (or failed) — update the live entry."""
    for c in _customs:
        if c.slug == slug:
            c.art = art


def environments() -> list[Environment]:
    """Authored environments, or the nine schema slugs as a titled fallback."""
    if _environments:
        return list(_environments)
    return [Environment(slug=s, name=s.replace("_", " ").title()) for s in ENVIRONMENT_SLUGS]


def environment_slugs() -> list[str]:
    return [e.slug for e in environments()]


def is_loaded() -> bool:
    return _loaded


def source_by_slug(slug: str) -> SourceCreature | None:
    return next((s for s in sources() if s.slug == slug), None)


def raw_source(slug: str) -> dict:
    """Full authored record for AI prompt enrichment ({} when unauthored)."""
    return _raw_sources.get(slug) or _raw_customs.get(slug) or {}


def raw_environment(slug: str) -> dict:
    """Full authored environment (sim block + advantages_hint) for battles."""
    return _raw_environments.get(slug, {})


def display_name(slug: str) -> str:
    """Pretty name for a slug, falling back to a title-cased slug."""
    found = source_by_slug(slug)
    return found.name if found else slug.replace("_", " ").replace("-", " ").title()


def validate_slugs(slugs: list[str]) -> list[str]:
    """Return the unknown slugs. Always empty while the library is unauthored."""
    if not _sources and not _customs:
        return []
    known = {s.slug for s in sources()}
    return [s for s in slugs if s not in known]
