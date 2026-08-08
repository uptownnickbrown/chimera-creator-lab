# UI Standard — the frame must deserve the paintings

Nick's verdict on the scaffold UI (2026-08-08): atrocious, ~20%. The creature
art is AAA; the HTML/CSS around it is flat cardboard. This document is the
binding standard for the presentation rebuild. Every screen ships only when a
1180×820 screenshot holds up NEXT TO its art-direction mock (side-by-side),
judged by the integration lead, not the implementing agent.

## The core principle

The pregenerated art IS the interface. CSS exists to arrange and frame
painted assets, never to substitute for them. If a surface looks like a CSS
rectangle, it is wrong.

## Layer stack (every screen, bottom to top)

1. **The lab**: `assets/lab/background.png` (or `background_arena.png` on
   battle screens) painted full-bleed, `background-size: cover`, fixed.
   Dimmed with a radial vignette overlay (darker at edges, subtle) so panels
   and creatures pop. NEVER a flat hex background color as the page ground.
2. **Atmosphere**: one slow ambient layer — drifting cyan particle motes
   (2 tiny CSS-animated layers, 60s loops, opacity ≤ .18, disabled under
   prefers-reduced-motion).
3. **Stage**: creatures ALWAYS stand on `assets/lab/platform.png` (gold
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
- **Codex** (`codex.png`): left filter rail (ALL/FAVORITES/WINNERS/BIGGEST/
  NEWEST with painted icons), center grid of creature cards (thumb, name
  plate, rarity chip, trophy count), right selected-creature panel with
  hero-on-platform, stats, records, GO TO ARENA.
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

For each screen: Playwright screenshot at 1180×820 AND 1440×900 →
compose side-by-side with the mock → the lead reviews and either signs off
or returns specific defects. Repeat until signed. Console must be
error-free; every Asset slot must resolve (zero magenta outlines).
