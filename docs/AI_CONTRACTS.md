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

**Stage B — hero render (gpt-image-2.5-flare, quality=high, background=transparent,
1536×1024, ~20s).** Prompt = STYLE constant (realistic AAA creature concept
art, one coherent species, dynamic pose, no gore, NO TEXT) + `visual_spec`.
Runs as soon as Stage A lands; frontend polls `image_status`.
Failure: one retry high, then quality=medium (~14s), then a friendly "lab
is recharging" state with a retry button. Record is never lost. Quality of
the first two rungs is `CHIMERA_HERO_QUALITY` (default high; `xhigh` is the
premium tier at ~$0.075).

**Safety rejections (2026-09-20).** gpt-image (1.5 and 2.5 alike) refuses prompts that name
famous trademarked characters ("Your request was rejected by the safety
system", HTTP 400): Henry's summoned Charizard/Mewtwo/Eevee-family parts never
got a portrait, and heroes whose `visual_spec` said "Night Fury-style" burned
all three rungs on the identical prompt. A rejected prompt is now never
re-sent; each refusal moves to the next of four prompt variants, all written
by gpt-5.1 with the regex scrub on top: **named** (the pregen-shaped prompt),
**anonymous** (names, brands and "like <character>" comparisons out, every
physical detail kept), **cousin** (the filter knows Charizard, Mewtwo,
Blastoise and Umbreon by shape alone, so: same body plan, element, palette
family and pose, only the two or three signature details changed — the
player still gets the kind of beast they asked for), and **distinct** (a
clearly new species, last resort). Refused renders are not billed; each
rewrite is a few tenths of a cent. For hero renders only summoned-part names
and the creature's own name are scrubbed — curated names ("shark", "dragon")
are anatomy. Upstream, both the creature SYSTEM_PROMPT and the summon resolver
forbid franchise/character names in image descriptions. Summoned parts whose
render failed report `portrait_status: failed` (TAP TO REPAINT in the lab,
`POST /api/library/custom/{slug}/retry-portrait`), and every boot re-renders
any part still missing art (`summon.resweep_portraits`, two at a time).

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

## 3. Championship key art (gpt-image-2.5-flare `images.edit`, ~22s)

Input: both finalists' hero cutouts + finals environment. Prompt pins
identity: "Keep BOTH creatures' designs EXACTLY as shown — same anatomy,
colors, plates, proportions." Validated in bakeoff (`keyart_finals.png`).
Generated during the semifinal→final transition so the ceremony never waits.
Failure: composited finale (the standard battle presentation) — never blocks.

## 4. Pregenerated assets (gpt-image — OpenAI everywhere)

Environments (9 arenas, opaque scenes), source-creature portraits, UI chrome,
fusion chamber, trophies. Cutout-style assets use native transparent
background — the Agora chroma-key/flood-fill pipeline is retired entirely.
Every part portrait (pregenerated or summoned) is stored TIGHT (alpha bbox)
at 512px on the long side, WebP q85 (`images.normalize_portrait`; the boot
pass in `summon.resweep_portraits` re-cuts the media volume whenever
`TIGHT_MARKER` is bumped). 512 covers the largest well (168px, 2× DPR) and
cut the library from 42MB to ~10MB (UI_STANDARD §Image delivery).
One style anchor generated first, then `images.edit` with the anchor as
reference keeps the set consistent. Pregen batches run offline in parallel;
per-image latency doesn't matter.

## Cost model (measured 2026-09-20, gpt-image-2.5-flare)

Image models bill output tokens ($30/M on gpt-image-2.5, $32/M on 1.5), and
the 2.5 models spend far fewer of them per quality tier — the bakeoff
(`research/bakeoff/run_2_5.py`, our own hero and part prompts) measured a
1536×1024 hero at low / medium / high / xhigh ≈ 158 / 343 / 1,372 / 2,459
output tokens ≈ $0.006 / $0.012 / $0.042 / $0.075, against 6,642 tokens
($0.21) for the 1.5 "high" that shipped before, with better-looking output
at every tier at or above medium. A 1024² part portrait at medium is ≈ $0.014
(was $0.046). gpt-5.1 is $1.25/M in, $10/M out with `reasoning_effort` none,
so every text call is a few tenths of a cent. Per unit of play:

| Unit | Calls | ≈ Cost | Was (1.5) |
|---|---|---|---|
| New chimera | record (gpt-5.1) + hero (1536×1024 high) | $0.05 | $0.21 |
| Tournament | ≤7 uncached battles ($0.01 each) + finals key art (edit, high) | $0.13 | $0.25–0.30 |
| Summon (new part) | resolver + portrait (1024² medium) | $0.02 | $0.04 |
| Battle replay / cached matchup / codex / hall | none | $0 | $0 |

At the week-of-2026-09-14 pace (~50 chimeras, ~7 tournaments, ~20 summons)
that is ≈ $4/week, down from ≈ $14. Levers: `CHIMERA_HERO_QUALITY=xhigh`
(+$0.03/chimera, the premium tier) or `medium` (−$0.03, visibly softer);
`CHIMERA_KEYART_QUALITY` likewise. Both are Railway env vars read at call
time. Failed image calls (safety rejections) are not billed.

## Cost/latency ledger (measured 2026-09-20)

| Job | Model | Latency |
|---|---|---|
| Creature record | gpt-5.1 | ~16s |
| Hero render high | gpt-image-2.5-flare | ~20s (was ~41s on 1.5) |
| Hero render medium (fallback) | gpt-image-2.5-flare | ~14s |
| Part portrait medium | gpt-image-2.5-flare | ~13s |
| Battle resolution | gpt-5.1 | ~15s (once per pair+env, then cached) |
| Finals key art | gpt-image-2.5-flare edit | ~22s (pre-generated during semis) |
