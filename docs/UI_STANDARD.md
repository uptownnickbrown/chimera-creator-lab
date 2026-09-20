# UI Standard — the frame must deserve the paintings

Nick's verdict on the scaffold UI (2026-08-08): atrocious, ~20%. The creature
art is AAA; the HTML/CSS around it is flat cardboard. This document is the
binding standard for the presentation rebuild. Every screen ships only when a
WebKit iPad screenshot (1080×810 — the real 9th-gen landscape viewport) holds
up NEXT TO its art-direction mock (side-by-side), judged by the integration
lead, not the implementing agent.

## The core principle

Quality and vibe over technology (Nick, direct quote: "I care about quality
and vibe, not technology"). There is nothing wrong with HTML/CSS — there is
everything wrong with half-assed. A CSS surface is welcome when it is
CRAFTED: layered gradients, bevel light, glow, depth, considered spacing —
indistinguishable in care from the painted assets beside it. A CSS surface
is wrong when it looks like a default rectangle someone stopped working on.
When a painted asset would sell the fantasy harder than code can, make the
asset — the pipeline is one script away. Every pixel earns its place; be
proud of every screen.

## Layer stack (every screen, bottom to top)

1. **The lab**: `assets/lab/background.webp` (or `background_arena.webp` on
   battle screens) painted full-bleed, `background-size: cover`, fixed.
   Dimmed with a radial vignette overlay (darker at edges, subtle) so panels
   and creatures pop. NEVER a flat hex background color as the page ground.
2. **Atmosphere**: one slow ambient layer — drifting cyan particle motes
   (2 tiny CSS-animated layers, 60s loops, opacity ≤ .18, disabled under
   prefers-reduced-motion).
3. **Stage**: creatures ALWAYS stand on `assets/lab/platform.webp` (gold
   variant for champions). Platform sits under the creature with a soft
   ellipse shadow bridging them. Creature renders come from /media (runtime)
   or assets/parts (library) — transparent PNGs over the platform, never in
   a box.
4. **Panels**: the holo-panel recipe below. Panels frame the stage; they
   never cover the creature.
5. **Typography + icons**: painted icons from assets/icons + the type system.

## Holo-panel recipe (the ONLY panel style)

```css
background: linear-gradient(165deg, rgba(24,36,84,.55), rgba(8,12,32,.78));
border: 1px solid rgba(79,216,255,.35);
border-radius: 14px;
box-shadow: inset 0 1px 0 rgba(140,220,255,.25),   /* top bevel light */
            0 0 24px rgba(79,216,255,.10),          /* outer glow */
            0 8px 32px rgba(0,0,0,.45);             /* depth */
backdrop-filter: blur(6px);
```
Plus: a 2px accent notch (clip-path corner cut) top-left and bottom-right —
the mocks' angular sci-fi corners. Section headers inside panels get a thin
gradient underline (cyan→transparent). Purple accent variant for
creation/fusion contexts, gold variant for champion contexts. Build these as
three utility classes; no bespoke panel styles per screen.

## Typography

- Display (headings, creature names, buttons): **Rajdhani** 600/700 via
  @fontsource (bundled, no CDN), uppercase, letter-spacing .06-.12em.
  Creature names on reveal get a cyan→violet gradient fill + soft glow.
- Body/UI: **Inter** via @fontsource. Stats and numerals: tabular-nums.
- Approved as the ONE new frontend dependency class (@fontsource/*).

## Buttons

Primary actions are painted-feel plates: gradient fill (violet for create,
teal for navigate, gold for arena/champion), 2px glow border, angular
corner cuts, hover = glow intensifies + 2% scale, active = press down 1px.
Min target 48px. Icon (painted asset) + Rajdhani label.

## Iconography

Only painted assets from `assets/icons`, `assets/trophy`, `assets/ui`, sized
20-32px inline. The Asset component's SLOT_ALIASES table is the single
mapping; a missing slot in dev renders a visible magenta outline (we WANT to
see gaps, not hide them politely).

## Portrait alignment (source-part art, 2026-09-20)

Every part portrait — the 160 pregenerated ones under `assets/parts` and every
summoned one under `/media/parts` — is stored as a TIGHT alpha crop: trimmed
to the creature's own bounding box, any aspect ratio, no baked-in canvas or
margin (`backend/app/services/images.py` `normalize_portrait`; the committed
library was re-cut with `scripts/normalize_portraits.py`; the media volume is
normalized once at boot). A square canvas centred each creature at whatever
height its silhouette happened to land, so Henry's rail read as a row of
creatures floating at different heights, some kissing the card edge.

With a tight image the CONTEXT decides the spacing, and the rule is:

- **Cards and wells** (picker rail, part slots, summon candidates, FUSED
  FROM tiles): `object-fit: contain; object-position: 50% 100%` inside an
  even inset (10-12px, or ~8% on small wells). Every creature's feet land on
  the same ground line; wide creatures sit low and whole, tall ones stand
  tall. A soft cyan floor ellipse under the feet (`.pcard__art::before`) is
  the lab's lit floor. Never `cover`: a cropped head reads as sloppy.
- **Orbs and circles** (proto-fusion cluster, Fusion Wait orbiters and
  source spots, tiny 34px chips): `object-fit: contain`, centred, at
  84-100% of the circle — the whole creature inside the ring.
- **Never** size a portrait by its pixel dimensions: they vary by creature.
  Size the box, let `contain` do the rest.

Hero renders and their derived 512px thumbnails are a separate pipeline
(alpha-fit onto a square with a small margin) and keep their own rules.

## Per-screen composition (vs art-direction mocks)

- **Home** (`welcome.png`): featured creature (most recent champion or
  newest) LARGE on the platform center, greeting + START BUILDING left,
  Quick Stats panel right, four action cards bottom-right in their signature
  colors (create=violet, codex=blue, arena=teal, hall=gold), Today's Crew
  row bottom-left with real thumbs.
- **Fusion Lab** (`build.png`): 4 part slots left as framed cards with
  portraits; center holo-silhouette preview on platform; right "what each
  part adds" panel; bottom horizontal picker rail of BIG portrait cards
  (~160px) with category tabs and name plates; RANDOMIZE + NEXT STEP.
- **Reveal** (`created.png`): already specced in the Fusion Wait build;
  restyle to this standard.
- **Codex** (`codex.png`, superseded 2026-08-09 — two panes, not three
  zones): narrow left LIST of creature rows (art well, name, rarity chip,
  trophy count) with sort pills above and a painted-progress footer; wide
  right dossier — hero render beside the record/stats/plaques column, FUSED
  FROM wells, all moves as always-visible cards (name + blurb), STRONG AT /
  WATCH OUT as full-sentence columns, fun fact as an always-open gold
  callout. Nothing in the dossier hides behind a tap.
- **Battle/Bracket** (`battle.png`): two creatures on side platforms facing
  inward (loser's side dims after resolve), environment art as the arena
  backdrop panel, prediction = two GIANT tap targets, result = winner
  laurel + three reason cards + health bars, bracket tree right rail,
  champion tracker gold panel.
- **Hall of Champions**: gold treatment, pedestal asset, champion on
  platform_gold, record plaques.

## Motion

Every screen transition: 200ms fade+4px rise. Panel content: staggered
60ms cascade on mount. Creature reveals: scale 0.92→1 with soft light bloom.
Nothing bounces except the rarity stamp. prefers-reduced-motion: fades only.

## Acceptance loop (non-negotiable)

For each screen: Playwright screenshot on WEBKIT with the iPad (gen 7/9)
landscape descriptor (1080×810, DPR 2, touch) AND Chromium at 1440×900 →
compose side-by-side with the mock → the lead reviews and either signs off
or returns specific defects. Repeat until signed. Console must be
error-free; every Asset slot must resolve (zero magenta outlines).

Mobile-Safari lesson (2026-08-09): Chromium at 1180×820 predicted neither the
real 1080px width nor WebKit layout — Henry's iPad showed truncated labels,
compressed grid rows and panels painting over footers that the sweep never
saw. scripts/qa_screens.py now runs the WebKit iPad profile and audits every
screen for clipped text, boxes escaping their parents, overlapping
interactive/panel boxes, and horizontal overflow. All four counts must be
ZERO on every screen before sign-off; the fitted desktop grids flow-and-
scroll below 1100px instead of squeezing (see the ≤1100 structural pass in
theme.css).

Real-device lesson (2026-09-20): Henry's iPad runs iPadOS 16.6 (the Railway
request logs say `Version/16.6 Safari`), three years behind Playwright's
WebKit. That engine resolves an in-flow image's `height: 100%` inside an
auto grid row as `auto`, so the image takes its intrinsic size and grows out
of its well — the slot-card portraits painted over their name plates while
the sweep was clean. Two rules follow: (1) every media well positions its
image absolutely and sizes it in percent of the well (one shared rule block
in theme.css, above `.slot__art`), or gives itself one definite row
(`grid-template-rows: 100%`, the stage fix); (2) the sweep's `imgrisk` audit
simulates the old engine by giving every in-flow image an auto height for a
moment and flagging any that would outgrow its parent — it must be ZERO
too. Vendor prefixes for that Safari (`-webkit-backdrop-filter` and friends)
come from autoprefixer with the `browserslist` in frontend/package.json;
without them none of the holo-panel blurs rendered on the device. A photo
from the iPad outranks the sweep.
