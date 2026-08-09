"""scripts/scrub_records.py — detection + rewrite plumbing, stubbed AI only.

The real gpt-5.1 rewriter is exercised by the lead at deploy time (and against
data/seed in the repo); tests inject a stub rewriter and never touch the
network.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import scrub_records as scrub

from app.schemas import (
    FUN_FACT_MAX,
    FUN_FACT_TARGET,
    TRAIT_MAX,
    TRAIT_TARGET,
    CreatureRecord,
)
from app.services.generation import build_stub_record

#: The live-data bug, verbatim shape: schema fragments glued into copy.
DEBRIS = 'environment_affinities":ing and surfacing habits make it easy prey rarity:"Legendary'


def _dirty_record() -> dict:
    record = build_stub_record(["dragon", "shark", "cobra", "octopus"]).model_dump()
    record["fun_fact"] = "It once " + "swam and swam " * 40 + "around the whole ocean."
    record["weaknesses"][1] = DEBRIS
    record["abilities"][0]["blurb"] = "A" + "n extremely long ability blurb" * 10
    return record


async def _stub_rewriter(name: str, offenses) -> dict[str, str]:
    return {o.path: f"Short kid line for {o.path}." for o in offenses}


# -- detection ------------------------------------------------------------------

def test_stub_records_are_already_clean():
    record = build_stub_record(["dragon", "shark", "cobra", "octopus"]).model_dump()
    assert scrub.find_offenses(record) == []


def test_find_offenses_flags_budget_and_debris():
    offenses = scrub.find_offenses(_dirty_record())
    by_path = {o.path: o for o in offenses}
    assert set(by_path) == {"fun_fact", "weaknesses[1]", "abilities[0].blurb"}

    assert any("over budget" in r for r in by_path["fun_fact"].reasons)
    assert by_path["fun_fact"].limit == FUN_FACT_TARGET
    # The observed Stormhorn Leviathan debris is caught even under budget.
    assert "json debris" in by_path["weaknesses[1]"].reasons
    assert by_path["weaknesses[1]"].limit == TRAIT_TARGET


def test_debris_patterns_match_the_live_bug():
    assert scrub.has_debris(DEBRIS)
    assert scrub.has_debris('its shell rarity:"Legendary hide')
    assert scrub.has_debris('strong tail": smashes rocks')
    assert not scrub.has_debris("Shrugs off the first big hit every time")
    assert not scrub.has_debris("Fights best at dawn: quick and quiet")  # a bare colon is fine


# -- rewrite plumbing --------------------------------------------------------------

async def test_scrub_record_rewrites_only_offending_fields():
    record = _dirty_record()
    untouched_strengths = list(record["strengths"])
    untouched_name = record["name"]

    fixed = await scrub.scrub_record("Testling", record, _stub_rewriter)
    assert {o.path for o in fixed} == {"fun_fact", "weaknesses[1]", "abilities[0].blurb"}

    assert record["fun_fact"] == "Short kid line for fun_fact."
    assert record["weaknesses"][1] == "Short kid line for weaknesses[1]."
    assert record["abilities"][0]["blurb"] == "Short kid line for abilities[0].blurb."
    assert record["strengths"] == untouched_strengths  # clean fields never touched
    assert record["name"] == untouched_name

    # Idempotent: a scrubbed record is clean, so a second pass is a no-op.
    assert scrub.find_offenses(record) == []
    assert await scrub.scrub_record("Testling", record, _stub_rewriter) == []


def _reads_as_a_whole_thought(text: str) -> bool:
    """No dangling fragment: a trimmed line must not end on a stop-word +
    period, which is what mid-thought truncation produces ("turning it into a.")."""
    if text.rstrip().endswith("…"):
        return True  # an ellipsis is honest truncation, not a faked sentence
    tail = text.rstrip(".!?").split()[-1].lower() if text.strip() else ""
    return tail not in {
        "a", "an", "the", "and", "or", "but", "of", "to", "in", "into", "with",
        "for", "so", "that", "its", "it", "is", "was", "can", "even",
    }


async def test_overlong_ai_rewrite_is_capped_at_the_schema_max_not_mangled():
    """A model that ignores the budget must never yield an invalid record —
    but the fix is a cap at the schema backstop, never a mid-sentence chop."""
    async def bad_rewriter(name, offenses):
        return {o.path: "word " * 200 for o in offenses}  # AI ignored the budget

    record = _dirty_record()
    await scrub.scrub_record("Testling", record, bad_rewriter)
    assert not scrub.has_debris(record["fun_fact"])
    assert len(record["fun_fact"]) <= FUN_FACT_MAX
    for w in record["weaknesses"]:
        assert len(w) <= TRAIT_MAX
    CreatureRecord.model_validate(record)  # always schema-valid


async def test_missing_rewrite_never_produces_a_truncated_fragment():
    """When the AI returns nothing, keeping a coherent over-target sentence
    beats chopping it — the record stays readable and schema-valid."""
    async def partial_rewriter(name, offenses):
        return {}  # AI returned nothing usable

    record = _dirty_record()
    await scrub.scrub_record("Testling", record, partial_rewriter)
    assert not scrub.has_debris(record["weaknesses"][1])  # debris ALWAYS removed
    CreatureRecord.model_validate(record)
    for field_text in (record["fun_fact"], record["weaknesses"][1],
                       record["abilities"][0]["blurb"]):
        assert _reads_as_a_whole_thought(field_text), field_text


# -- seed-pack scrubbing -------------------------------------------------------------

def _build_seed(tmp_path: Path) -> Path:
    seed_dir = tmp_path / "seed"
    clean = build_stub_record(["dragon", "shark", "cobra", "octopus"]).model_dump()
    dirty = _dirty_record()
    for key, record in (("clean_one", clean), ("dirty_one", dirty)):
        entry = seed_dir / key
        entry.mkdir(parents=True)
        (entry / "record.json").write_text(json.dumps(
            {"key": key, "sources": ["dragon", "shark", "cobra", "octopus"],
             "record": record}
        ))
    return seed_dir


async def test_scrub_seed_dry_run_changes_nothing(tmp_path):
    seed_dir = _build_seed(tmp_path)
    before = (seed_dir / "dirty_one" / "record.json").read_text()
    assert await scrub.scrub_seed(seed_dir, _stub_rewriter, dry_run=True) == 1
    assert (seed_dir / "dirty_one" / "record.json").read_text() == before


async def test_scrub_seed_fixes_writes_back_and_is_idempotent(tmp_path):
    seed_dir = _build_seed(tmp_path)
    clean_before = (seed_dir / "clean_one" / "record.json").read_text()

    assert await scrub.scrub_seed(seed_dir, _stub_rewriter, dry_run=False) == 1
    assert (seed_dir / "clean_one" / "record.json").read_text() == clean_before

    payload = json.loads((seed_dir / "dirty_one" / "record.json").read_text())
    assert payload["key"] == "dirty_one"  # wrapper shape preserved
    assert payload["sources"] == ["dragon", "shark", "cobra", "octopus"]
    record = CreatureRecord.model_validate(payload["record"])  # still boot-loadable
    assert scrub.find_offenses(record.model_dump()) == []

    assert await scrub.scrub_seed(seed_dir, _stub_rewriter, dry_run=False) == 0


# -- DB scrubbing ---------------------------------------------------------------------

def _build_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "scratch.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE creatures (id INTEGER PRIMARY KEY, name TEXT, title TEXT, "
        "fun_fact TEXT, strengths TEXT, weaknesses TEXT, abilities TEXT)"
    )
    clean = build_stub_record(["dragon", "shark", "cobra", "octopus"]).model_dump()
    dirty = _dirty_record()
    for i, r in enumerate((clean, dirty), start=1):
        conn.execute(
            "INSERT INTO creatures VALUES (?, ?, ?, ?, ?, ?, ?)",
            (i, r["name"], r["title"], r["fun_fact"], json.dumps(r["strengths"]),
             json.dumps(r["weaknesses"]), json.dumps(r["abilities"])),
        )
    conn.commit()
    conn.close()
    return db_path


async def test_scrub_db_fixes_dirty_rows_and_is_idempotent(tmp_path):
    db_path = _build_db(tmp_path)

    assert await scrub.scrub_db(db_path, _stub_rewriter, dry_run=True) == 1
    assert await scrub.scrub_db(db_path, _stub_rewriter, dry_run=False) == 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM creatures WHERE id = 2").fetchone()
    conn.close()
    assert row["fun_fact"] == "Short kid line for fun_fact."
    assert json.loads(row["weaknesses"])[1] == "Short kid line for weaknesses[1]."
    assert json.loads(row["abilities"])[0]["blurb"] == "Short kid line for abilities[0].blurb."

    assert await scrub.scrub_db(db_path, _stub_rewriter, dry_run=False) == 0
