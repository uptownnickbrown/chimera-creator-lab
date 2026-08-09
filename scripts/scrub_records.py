"""Retroactive kid-length scrub for creature records (playtest request #2/#9).

Two real-data problems observed live:
  1. JSON debris glued into copy (Stormhorn Leviathan's weakness contained
     `environment_affinities":ing and surfacing habits ... rarity:"Legendary`).
  2. Strengths/weaknesses/blurbs running 500+ characters — walls no kid reads.

This script scans a target sqlite DB (``--db`` — REQUIRED for DB scrubbing,
deliberately NO default so it can never silently touch the live game) and/or
the committed seed pack (``data/seed/*/record.json``). For every creature with
a field over budget (schemas.py *_TARGET) or containing JSON-artifact debris,
ONE gpt-5.1 structured-output call rewrites only the offending fields — same
meaning, kid tone, within budget — and writes them back.

Resumable / idempotent: each creature is committed as it is fixed, and clean
records are never touched, so re-running converges to a no-op.

Usage:
    .venv/bin/python scripts/scrub_records.py --dry-run              # seed pack only
    .venv/bin/python scripts/scrub_records.py                        # scrub seed pack
    .venv/bin/python scripts/scrub_records.py --db /path/game.db     # DB + seed pack
    .venv/bin/python scripts/scrub_records.py --db /path/game.db --skip-seed
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.schemas import (
    ABILITY_BLURB_MAX,
    ABILITY_BLURB_TARGET,
    FUN_FACT_MAX,
    FUN_FACT_TARGET,
    TITLE_MAX,
    TITLE_TARGET,
    TRAIT_MAX,
    TRAIT_TARGET,
    CreatureRecord,
    Strict,
)

SEED_DIR = REPO / "data" / "seed"

# -- detection ------------------------------------------------------------------

#: Schema fragments the model has been observed gluing into copy. Any hit makes
#: a field "dirty" regardless of its length.
_KEY_FRAGMENT_RE = re.compile(
    r"\b(?:rarity|environment_affinities|sim_profile|core_stats|visual_spec"
    r"|anatomy_plan|fun_fact|strengths|weaknesses|abilities|special_name)\s*:"
)
DEBRIS_PATTERNS = (
    re.compile(r'"\s*:'),   # `":`  — key/value glue
    re.compile(r':\s*"'),   # `:"`  — e.g. rarity:"Legendary
    _KEY_FRAGMENT_RE,       # schema key names glued into copy
    re.compile(r"[{}]"),    # braces never belong in kid copy
)


@dataclass
class Offense:
    path: str      # "title" | "fun_fact" | "strengths[1]" | "abilities[2].blurb"
    limit: int     # SOFT character budget (the prompt TARGET)
    text: str
    hard_max: int = 0   # schema backstop; only this is enforced destructively
    reasons: list[str] = field(default_factory=list)


def _budgeted_fields(record: dict):
    """Yield (path, limit, text) for every budgeted string in a record dict."""
    yield "title", TITLE_TARGET, TITLE_MAX, record.get("title") or ""
    yield "fun_fact", FUN_FACT_TARGET, FUN_FACT_MAX, record.get("fun_fact") or ""
    for key in ("strengths", "weaknesses"):
        for i, text in enumerate(record.get(key) or []):
            yield f"{key}[{i}]", TRAIT_TARGET, TRAIT_MAX, text or ""
    for i, ability in enumerate(record.get("abilities") or []):
        yield (f"abilities[{i}].blurb", ABILITY_BLURB_TARGET, ABILITY_BLURB_MAX,
               (ability or {}).get("blurb") or "")


def has_debris(text: str) -> bool:
    return any(rx.search(text) for rx in DEBRIS_PATTERNS)


def find_offenses(record: dict) -> list[Offense]:
    out: list[Offense] = []
    for path, limit, hard_max, text in _budgeted_fields(record):
        reasons = []
        if len(text) > limit:
            reasons.append(f"over budget ({len(text)} > {limit})")
        if has_debris(text):
            reasons.append("json debris")
        if reasons:
            out.append(Offense(path=path, limit=limit, text=text,
                               hard_max=hard_max, reasons=reasons))
    return out


# -- applying rewrites ------------------------------------------------------------

_PATH_RE = re.compile(r"^(title|fun_fact)$|^(strengths|weaknesses)\[(\d+)\]$"
                      r"|^abilities\[(\d+)\]\.blurb$")


def set_field(record: dict, path: str, text: str) -> None:
    m = _PATH_RE.match(path)
    if m is None:
        raise ValueError(f"unknown field path {path!r}")
    if m.group(1):
        record[m.group(1)] = text
    elif m.group(2):
        record[m.group(2)][int(m.group(3))] = text
    else:
        record["abilities"][int(m.group(4))]["blurb"] = text


def hard_trim(text: str, limit: int, *, must_fit: bool = False) -> str:
    """Shorten deterministically, preferring meaning over the character count.

    Order: real sentence end → clause edge → (if the limit is soft) keep the
    coherent original → honest ellipsis. It must NEVER cut mid-thought and glue
    a period on, which is what produced live copy like "turning it into a."
    `must_fit=True` means `limit` is the schema backstop and cannot be exceeded.
    """
    text = text.replace('"', "").replace("{", "").replace("}", "")
    text = _KEY_FRAGMENT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;:-")
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer a real sentence end.
    for boundary in (". ", "! ", "? "):
        idx = cut.rfind(boundary)
        if idx >= int(limit * 0.5):
            return cut[: idx + 1].strip()
    # Then a clause edge — dropping a trailing clause still reads as English.
    idx = max(cut.rfind(", "), cut.rfind("; "))
    if idx >= int(limit * 0.5):
        return cut[:idx].rstrip(" ,;:-–—") + "."
    if not must_fit:
        # Over the soft target but coherent: leave it alone.
        return text
    # Schema backstop with no clean boundary anywhere: cut on a word edge and
    # say so with an ellipsis. Honest truncation, never a fake sentence end.
    cut = text[: max(1, limit - 1)]
    idx = cut.rfind(" ")
    if idx > 0:
        cut = cut[:idx]
    return cut.rstrip(" ,;:-–—") + "…"


def clean_rewrite(text: str, limit: int, hard_max: int | None = None) -> str:
    """Sanitize one AI rewrite.

    `limit` is the SOFT target the model was asked for — going slightly over
    is fine and always better than a chopped sentence. Only debris, or blowing
    past the schema's hard max, triggers surgery.
    """
    text = re.sub(r"\s+", " ", text.strip())
    if has_debris(text):
        text = hard_trim(text, hard_max or limit, must_fit=hard_max is not None)
    if hard_max and len(text) > hard_max:
        text = hard_trim(text, hard_max, must_fit=True)
    return text


# -- the gpt-5.1 rewriter ----------------------------------------------------------

class RewrittenField(Strict):
    path: str
    text: str


class ScrubRewrite(Strict):
    fields: list[RewrittenField]


SCRUB_SYSTEM = (
    "You polish creature-card text for Chimera Creator, a game played by a "
    "7-year-old. You receive fields that are too long or contain leaked JSON "
    "fragments (things like '\":' or 'rarity:\"Legendary' glued into a "
    "sentence). Rewrite EVERY field you are given:\n"
    "- keep the same core meaning (drop extra details, never invent new ones)\n"
    "- ONE short, punchy, exciting sentence a 7-year-old reads in one breath\n"
    "- STRICTLY UNDER the character budget given for that field\n"
    "- plain text only: no quotes, braces, colons, or schema key names\n"
    "- epic but never gory (defeated/knocked out, never killed; no blood)\n"
    "Return every field with its `path` EXACTLY as given."
)


async def rewrite_with_ai(creature_name: str, offenses: list[Offense]) -> dict[str, str]:
    """One structured-output call for one creature -> {path: rewritten text}."""
    from app.services import ai

    lines = [
        f"- path: {o.path}\n  budget: {o.limit} characters\n  current text: {o.text}"
        for o in offenses
    ]
    user = (
        f"Creature: {creature_name!r}. Rewrite these {len(offenses)} field(s):\n\n"
        + "\n".join(lines)
    )
    result = await ai.structured(SCRUB_SYSTEM, user, ScrubRewrite, name="scrub")
    return {f.path: f.text for f in result.fields}


async def scrub_record(name: str, record: dict, rewriter) -> list[Offense]:
    """Fix one record dict in place; returns the offenses that were fixed."""
    offenses = find_offenses(record)
    if not offenses:
        return []
    rewrites = await rewriter(name, offenses)
    for offense in offenses:
        raw = rewrites.get(offense.path)
        text = (clean_rewrite(raw, offense.limit, offense.hard_max) if raw
                else clean_rewrite(offense.text, offense.limit, offense.hard_max))
        set_field(record, offense.path, text)
    return offenses


# -- targets ------------------------------------------------------------------------

def _report(label: str, name: str, offenses: list[Offense], *, dry: bool) -> None:
    verb = "would fix" if dry else "fixed"
    print(f"[{label}] {name}: {verb} {len(offenses)} field(s)")
    for o in offenses:
        print(f"    {o.path:<24} {', '.join(o.reasons)}")
        print(f"        {o.text[:100]!r}{'…' if len(o.text) > 100 else ''}")


async def scrub_seed(seed_dir: Path, rewriter, *, dry_run: bool) -> int:
    """Scrub data/seed/*/record.json. Returns count of records changed."""
    changed = 0
    for record_path in sorted(seed_dir.glob("*/record.json")):
        payload = json.loads(record_path.read_text())
        record = payload["record"]
        key = record_path.parent.name
        if dry_run:
            offenses = find_offenses(record)
            if offenses:
                _report("seed", f"{key} {record.get('name')!r}", offenses, dry=True)
                changed += 1
            continue
        offenses = await scrub_record(record.get("name") or key, record, rewriter)
        if offenses:
            CreatureRecord.model_validate(record)  # never write back a broken record
            record_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            _report("seed", f"{key} {record.get('name')!r}", offenses, dry=False)
            changed += 1
    return changed


#: creatures-table columns the scrub may touch, in _budgeted_fields shape.
_DB_JSON_COLS = ("strengths", "weaknesses", "abilities")
_DB_TEXT_COLS = ("title", "fun_fact")


async def scrub_db(db_path: Path, rewriter, *, dry_run: bool) -> int:
    """Scrub the creatures table of a sqlite DB. Returns rows changed.

    Commits row by row, so an interrupted run resumes cleanly: already-fixed
    creatures are clean and skipped on the next pass.
    """
    if not db_path.exists():
        raise SystemExit(f"--db {db_path}: no such file")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    changed = 0
    try:
        rows = conn.execute(
            "SELECT id, name, title, fun_fact, strengths, weaknesses, abilities "
            "FROM creatures ORDER BY id"
        ).fetchall()
        for row in rows:
            record = {
                "title": row["title"] or "",
                "fun_fact": row["fun_fact"] or "",
                **{c: json.loads(row[c]) if row[c] else [] for c in _DB_JSON_COLS},
            }
            name = row["name"] or f"creature {row['id']}"
            if dry_run:
                offenses = find_offenses(record)
                if offenses:
                    _report("db", f"#{row['id']} {name!r}", offenses, dry=True)
                    changed += 1
                continue
            offenses = await scrub_record(name, record, rewriter)
            if not offenses:
                continue
            conn.execute(
                "UPDATE creatures SET title=?, fun_fact=?, strengths=?, weaknesses=?, "
                "abilities=? WHERE id=?",
                (
                    record["title"], record["fun_fact"],
                    *(json.dumps(record[c]) for c in _DB_JSON_COLS),
                    row["id"],
                ),
            )
            conn.commit()
            _report("db", f"#{row['id']} {name!r}", offenses, dry=False)
            changed += 1
    finally:
        conn.close()
    return changed


# -- CLI ------------------------------------------------------------------------------

async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--db", type=Path, default=None,
        help="sqlite DB to scrub (REQUIRED for DB scrubbing — no default, ever)",
    )
    parser.add_argument(
        "--seed-dir", type=Path, default=SEED_DIR,
        help=f"seed pack to scrub (default {SEED_DIR})",
    )
    parser.add_argument("--skip-seed", action="store_true", help="do not touch the seed pack")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="list what would change; no AI calls, no writes",
    )
    args = parser.parse_args()

    if args.db is None and args.skip_seed:
        parser.error("nothing to do: pass --db and/or drop --skip-seed")

    if not args.dry_run:
        from app.services import ai

        if not ai.ai_enabled():
            raise SystemExit(
                "OPEN_AI_API_KEY not available (or CHIMERA_STUB_AI=1) — the scrub "
                "rewrites with gpt-5.1 and refuses to run without it. Use --dry-run "
                "to inspect."
            )

    total = 0
    if not args.skip_seed:
        total += await scrub_seed(args.seed_dir, rewrite_with_ai, dry_run=args.dry_run)
    if args.db is not None:
        total += await scrub_db(args.db, rewrite_with_ai, dry_run=args.dry_run)
    verb = "need scrubbing" if args.dry_run else "scrubbed"
    print(f"done: {total} record(s) {verb}")


if __name__ == "__main__":
    asyncio.run(_main())
