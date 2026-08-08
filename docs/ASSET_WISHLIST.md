# Asset Wishlist — Chimera Creator

Every pregenerated asset slot, Agora-style: define → generate all ahead of
time → frontend `Asset` component loads `/assets/<slot>.png` with a styled
fallback until the PNG lands. All generation via **gpt-image-1.5** (OpenAI
everywhere). Cutout assets use `background=transparent`; scenes are opaque.
NO text baked into any image — UI renders all typography. No emoji anywhere.

## Style anchor (prepend to every prompt)

> Cinematic sci-fi game art for a neon "creature laboratory" interface aimed
> at kids 7–10. Deep navy and black environments, electric cyan and blue
> holographic light, violet-purple fusion energy as the signature accent,
> gold reserved for champions and trophies. Clean industrial sci-fi surfaces,
> glass and brushed dark metal, glowing circuit filigree, volumetric light.
> Epic and premium, never scary or gory. No text, letters, numbers,
> watermarks, or UI widgets in the image.

Reference mocks: `art-direction/*.png` (canonical look). First-generated
asset of each family becomes the `images.edit` reference for the rest.

## 1. Environments — battle arenas (9, opaque, 1536×1024 → also 640×360 crop)

`env/<slug>.png` + `env/<slug>_card.png` for: storm-coast, deep-ocean,
volcanic-shore, jungle-canyon, frozen-ridge, open-sky, desert-ruins, swamp,
city-harbor. Prompt = anchor + `visual_hint` from data/environments.json +
"wide establishing shot of an epic monster battle arena, no creatures
present, dramatic depth, space at center for two large combatants."

## 2. Source-part portraits (95, transparent, 1024×1024 → shown ~200px)

`parts/<slug>.png` — one per data/source_creatures.json entry. Prompt =
anchor-lite (realistic creature, neon rim-light treatment) + `visual_hint` +
"single creature portrait, three-quarter view, dramatic pose, full body,
centered, transparent background." Batch-parallel; consistency via one style
reference (generate `parts/dragon.png` first, feed as reference).
Rule reminder: realistic creatures with cyan/violet rim light — NOT neon
holograms; variety of natural coloring must survive.

## 3. Lab set pieces (transparent unless noted)

| Slot | Size | Description |
|---|---|---|
| `lab/platform.png` | 1536×640 | The holographic creature platform: concentric cyan light rings on dark glass base, seen from slight above-front. THE stage every creature stands on. |
| `lab/platform_gold.png` | 1536×640 | Champion variant: gold rings. |
| `lab/fusion_chamber.png` | 1024×1024 | Empty fusion chamber mid-activation: violet energy vortex between electrode arms, particles converging. Reveal-wait centerpiece. |
| `lab/background.png` | 1920×1080, opaque | The lab interior itself: dark depth, distant machinery bokeh, subtle cyan/violet glow. App backdrop. |
| `lab/background_arena.png` | 1920×1080, opaque | Arena variant with crowd-of-lights energy for battle screens. |

## 4. UI chrome (transparent)

| Slot | Size | Description |
|---|---|---|
| `ui/panel_corner.png` (9-slice set or CSS-borders instead — decide at build) | — | Holographic panel frame treatment; prefer CSS if it hits the bar. |
| `ui/slot_empty.png` | 512×512 | Empty fusion slot: dark socket with faint violet standby glow and a subtle "?" formed by circuitry (no typographic glyph). |
| `ui/btn_create.png` | 1024×320 | The CREATE CHIMERA button plate: violet energy core, beveled sci-fi frame (label rendered by UI). |
| `icons/stat_power.png, stat_speed.png, stat_armor.png, stat_size.png, stat_special.png` | 256×256 | Five stat glyphs: fist/impact burst, motion streaks, shield plates, scale silhouette, starburst. Bold, readable at 28px. |
| `icons/cat_mythic.png, cat_extinct.png, cat_living.png` | 256×256 | Picker category emblems: dragon sigil, fossil spiral, leaf-paw. |
| `icons/env_*.png` (wave, lightning, depth, dark, lava, heat, canyon, vines, ice, wind, sky, sand, ruins, mud, murk, docks, night) | 256×256 | Environment property glyphs used on battle cards — cover the union of icons in data/environments.json kid_properties. |

## 5. Trophies & ceremony (transparent)

| Slot | Size | Description |
|---|---|---|
| `trophy/champion_cup.png` | 1024×1024 | Gold holographic champion trophy, violet energy core. |
| `trophy/badge_champion.png` | 512×512 | Compact champion crest for Codex cards. |
| `trophy/laurel.png` | 1024×512 | Gold laurel wreath frame for the winner announcement. |
| `trophy/confetti_sheet.png` | 1024×1024 | Sparse gold/cyan energy-spark particles on transparency (CSS-animated). |
| `hall/pedestal.png` | 1024×768 | Hall of Champions display pedestal with gold uplight. |

## 6. Henry's world (transparent)

| Slot | Size | Description |
|---|---|---|
| `avatar/henry.png` | 512×512 | Kid scientist avatar in a lab coat with cyan goggles — friendly, heroic, cartoon-proportioned but rendered in the game's cinematic style. A few variants to pick from at first launch. |
| `lab/mascot.png` | 512×512 | Optional: small hovering lab drone/assistant bot for empty states and tips. |

## Numbers

~9 environments ×2 + 95 parts + ~10 lab/UI pieces + ~17 icons + ~6 ceremony
+ ~4 avatar/mascot ≈ **150 generations** (plus retries). At ~30s parallel ×8
workers ≈ under 2 hours wall-clock, run once. Raw renders kept in
`scripts/raw/` (gitignored); finished PNGs committed to
`frontend/public/assets/`.
