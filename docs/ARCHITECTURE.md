# Chimera Creator — Architecture

Single-player web game for Henry (age 7). Quality bar: AAA-feel, brag-worthy.
Stack mirrors Agora; audience of one, so no scaling complexity anywhere.

## Locked product decisions (Nick, 2026-08-08)

| Decision | Choice |
|---|---|
| Creature art | Realistic AAA movie-monster renders, text-free, transparent background, presented in neon-lab UI |
| Battles | **Fully deterministic**: same (A, B, environment) → same winner, forever. Cached permanently. |
| Recipe rule | Guided (picker encourages mythic/extinct/living/living; any four legal) |
| Creation latency | 30–60s, staged reveal (text fast → image resolves in fusion animation) |
| Battle visuals | Composited (hero cutouts + pregen environment art + FX overlays); generated key art for championship finals only |
| Access | Railway deploy, simple kid gate, personalized to Henry |
| Devices | Landscape iPad (1024×768) → desktop. Touch + mouse. No portrait phone. |

## Model roster (from bakeoff, research/bakeoff/)

| Role | Model | Why |
|---|---|---|
| Runtime creature hero render | **gpt-image-1.5**, `background=transparent`, high, 1536×1024 | Only model with native alpha; handles translucent flame/lightning/spray edges chroma-key never can; best drama. ~50s. |
| Creature record (text) | **gpt-5.1** structured output | Best fused abilities/weaknesses, kid-perfect copy, ~16s. |
| Battle resolution + narrative | **gpt-5.1** structured output | Deterministic contract needs strong reasoning over saved profiles. |
| Championship key art | **gpt-image-1.5 images.edit** with both hero cutouts as reference | Identity-preserving two-creature scene (validated in bakeoff). |
| Pregen UI/environment assets | **gpt-image-1.5** (transparent for cutout assets, opaque for scenes) | OpenAI-only everywhere (Nick, 2026-08-08): native alpha replaces the entire chroma-key pipeline; one SDK; pregen latency is irrelevant offline. |

No runtime degradation path (Nick, 2026-08-08): one AI integrated well is
plenty. Image failure = retry high → quality=medium → friendly "lab is
recharging" error. The Gemini key stays in .env for research only.

## Repo layout

```
backend/            Python 3.12, FastAPI, SQLAlchemy 2 async, SQLite dev / Postgres prod, Alembic
  app/
    api/            routers: creatures, battles, tournaments, codex, profile
    services/       generation.py (staged creature gen), battle.py (deterministic engine),
                    images.py (providers + alpha pipeline), library.py (source creatures)
    models.py       all tables in one file (Agora convention)
    schemas.py      pydantic contracts: CreatureRecord, BattleResult, etc.
  tests/
frontend/           React 18 + TS + Vite. Screens: Home, FusionLab, Reveal, Codex, Bracket, Battle, HallOfChampions
  public/assets/    pregenerated art (git-committed, like Agora)
scripts/            asset pipeline (assetlib port), qa_screenshots.py
research/bakeoff/   model evaluation artifacts (keep)
docs/
```

## Core flows

**Creation (staged):** POST /api/creatures {source_ids[4]} → server kicks off
gpt-5.1 record gen (~16s) and, as soon as the record's visual_spec exists,
gpt-image-1.5 hero render (~50s). Frontend polls status
(`pending_text → pending_image → complete`); fusion-chamber animation plays
throughout; name/stats/abilities reveal the moment text lands. On image
failure: retry once, then fallback provider; never lose the record.

**Determinism:** battle outcome = f(creatureA.id, creatureB.id, environment).
Computed once by gpt-5.1 with temperature 0-ish intent, then **stored forever**
in `battles` keyed (min_id, max_id, env). Replays read the cache — free, instant,
and guarantees the determinism promise even though LLMs aren't. Bracket UI
replays are instant; only first-ever matchups think.

**Codex:** every creature saved with full record + hero PNG (+ derived
thumbnail crop). Win/loss/champion records accumulate on the creature row.

**Source library is hybrid (Nick, 2026-08-08):** ~95 curated parts ship with
pregenerated portraits + hand-tuned traits (visual browsing default). PLUS
"Summon New Creature": Henry types ANY creature (real/extinct/mythic/invented)
→ gpt-5.1 generates its library entry (traits, kid_blurb, contributes, scale)
→ gpt-image-1.5 medium (~26s) paints its portrait → saved to his library
permanently as a first-class part. Custom parts table mirrors the curated
schema with `custom=true`. Kid-safety redirect (never a hard error) in the
summon prompt. API: POST /api/library/summon {name}.

## Non-negotiables

- Creature images contain **zero text**; UI renders all typography.
- Every LLM path degrades gracefully (Agora rule) — a failed generation never
  crashes a screen or strands a tournament.
- No emoji as UI iconography; painted/pregen assets only.
- Kid-safety constraints (spec §23) live in the system prompts: epic, no gore,
  "defeated/knocked out" language, age-appropriate names.
- All stats visible to Henry are 0–100; sim uses hidden richer profile.
```
