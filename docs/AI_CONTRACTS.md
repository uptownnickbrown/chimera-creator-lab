# AI Contracts

The three runtime AI jobs, their exact contracts, and the determinism story.
Bakeoff evidence: `research/bakeoff/` (report published as artifact).

## 1. Creature generation (staged)

**Stage A — record (gpt-5.1, structured output, ~16s).**
System prompt core (validated in `research/bakeoff/text_probe.py`):

> You are the creature engine for Chimera Creator, a game where a 7-year-old
> fuses four creatures into one spectacular new species. Invent ONE coherent
> species (never four animals stitched together). Best abilities fuse TWO
> sources (Shark + Electric Eel = Thunder Bite). Every creature needs real
> weaknesses — resist "awesome at everything". Stats 0–100 with honest spread.
> Kid-readable: short, punchy, epic but never gory.

Enriched at runtime with the four source-library entries (traits, scale,
movement, mythic powers) so interpretation stays stable. Output = the
CreatureRecord schema (schemas.py). `visual_spec` must be a complete
image-ready physical description.

**Stage B — hero render (gpt-image-1.5, quality=high, background=transparent,
1536×1024, ~50s).** Prompt = STYLE constant (realistic AAA creature concept
art, one coherent species, dynamic pose, no gore, NO TEXT) + `visual_spec`.
Runs as soon as Stage A lands; frontend polls `image_status`.
Failure: one retry high, then quality=medium (verified path, ~26s), then a
friendly "lab is recharging" state with a retry button. Record is never lost.

**Derived assets (local, instant):** alpha-aware bounding-box crop →
square thumbnail; cutout reused everywhere (Codex, battle compositing).

**Name reroll:** regenerate only `name` + `title` with the record as context,
temperature high, "give a DIFFERENT name than {current}". Never touches stats.

## 2. Battle resolution (gpt-5.1, structured output)

**Determinism is architectural, not model-level.** LLMs can't promise
bit-identical outputs, so the rule is: **first resolution wins, forever.**

- Canonical key: `min(idA,idB):max(idA,idB):environment`.
- On first request: resolve once, store the full BattleResult row.
- Every later request (rematch, bracket replay, sibling curiosity) reads the
  row. Same matchup + same environment = same winner, same reasons, same
  story. Instant and free.
- The prompt receives both full sim profiles + the environment's `sim` block
  and `advantages_hint`, and must produce: winner, confidence, exactly 3
  kid reasons ({icon keyword, title ≤4 words, blurb ≤12 words}), 4–6 battle
  beats, a short narrative, health_remaining. Reasons must reference concrete
  traits/environment interactions, not stat totals.
- Safety: "defeated / knocked out / driven back" language; no gore.

Battle order in a bracket never affects outcomes (each pair+env is
independent), so pre-resolving a whole bracket in parallel is legal and makes
the tournament feel instant after the first frame.

## 3. Championship key art (gpt-image-1.5 `images.edit`, ~74s)

Input: both finalists' hero cutouts + finals environment. Prompt pins
identity: "Keep BOTH creatures' designs EXACTLY as shown — same anatomy,
colors, plates, proportions." Validated in bakeoff (`keyart_finals.png`).
Generated during the semifinal→final transition so the ceremony never waits.
Failure: composited finale (the standard battle presentation) — never blocks.

## 4. Pregenerated assets (gpt-image-1.5 — OpenAI everywhere)

Environments (9 arenas, opaque scenes), source-creature portraits, UI chrome,
fusion chamber, trophies. Cutout-style assets use native transparent
background — the Agora chroma-key/flood-fill pipeline is retired entirely.
One style anchor generated first, then `images.edit` with the anchor as
reference keeps the set consistent. Pregen batches run offline in parallel;
per-image latency doesn't matter.

## Cost/latency ledger (measured 2026-08-08)

| Job | Model | Latency |
|---|---|---|
| Creature record | gpt-5.1 | ~16s |
| Hero render high | gpt-image-1.5 | ~50s |
| Hero render medium (fallback) | gpt-image-1.5 | ~26s |
| Battle resolution | gpt-5.1 | ~15s (once per pair+env, then cached) |
| Finals key art | gpt-image-1.5 edit | ~74s (pre-generated during semis) |
