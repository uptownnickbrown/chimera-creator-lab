# Chimera Creator
## Product Vision & Gameplay Design Brief

**Status:** Design/vision document approaching feature-spec detail  
**Primary audience:** Product, design, engineering, AI/ML, art, and game design  
**Target player:** Children roughly **7–10**, with a strong assumption that a seven-year-old should be able to understand the primary loop without adult explanation  
**Platform assumption:** Initially desktop/tablet-friendly web experience; interaction patterns should remain touch-compatible  
**AI assumption:** The product has access to a high-quality OpenAI API key and can use AI generation at runtime for creature concepting, naming, descriptions, statistics, battle reasoning, and imagery.

---

# 1. The One-Sentence Pitch

**Chimera Creator is a game where kids combine four wildly different creatures into one spectacular new monster, collect the creatures they invent, predict which ones will win in tournament battles, and build a personal Hall of Champions.**

The game should make the player repeatedly think:

1. **“I have to see what those four creatures turn into.”**
2. **“Whoa. That thing is awesome.”**
3. **“I bet mine beats yours.”**
4. **“Wait — why did THAT one win?”**

That emotional sequence is the product.

---

# 2. Product Thesis

The original concept combined several appealing ideas: creature creation, fantasy bestiaries, Pokémon-like abilities, stat comparison, monster tournaments, speculative biology, and playground arguments about which monster would win.

The refined product should **not** attempt to make all of those systems equally deep.

For a seven-year-old, the game succeeds if it does three things exceptionally well:

- makes creation feel magical;
- makes the resulting creature feel personally owned and worth revisiting;
- turns battle outcomes into understandable, debatable stories.

The game should therefore optimize for **wonder, ownership, prediction, and replay**, not for complex tactical combat.

This leads to an important simplification:

> **The player is primarily a creator and predictor, not a combat systems operator.**

The AI can handle the complicated reasoning underneath the surface. The child gets the fun decisions.

---

# 3. Audience and Age Philosophy

## Primary player

The experience should be usable by a confident **7-year-old** who enjoys animals, monsters, fantasy, collecting, or “who would win?” questions.

Older children and adults should still find the creature generation and matchup reasoning entertaining, but the primary interaction model should not depend on reading dense paragraphs, understanding RPG math, or managing many currencies and upgrade systems.

## Design consequences

### We should favor

- large creature art;
- large buttons;
- strong iconography;
- simple labels;
- 3–5 important stats rather than 12–20;
- short explanations with optional detail;
- obvious next actions;
- visual comparisons;
- celebratory reveals;
- clear tournament progress;
- direct feedback when a prediction is right or wrong.

### We should avoid

- dense RPG spreadsheets;
- tiny status-effect icons;
- complicated inventory management;
- multiple overlapping currencies;
- long battle logs as the primary battle experience;
- precise percentages everywhere;
- deep leveling/equipment trees in the first version;
- requiring the player to understand model-generated biological logic before they can have fun.

## Reading level

Critical UI copy should usually be short enough to scan rather than read closely.

Good:

- **Huge bite**
- **Fast in water**
- **Heavy armor**
- **Can fly**
- **Weak on land**

Less suitable as primary UI:

- “Superior hydrodynamic mobility provides a situational advantage against terrestrial opponents.”

The deeper explanation can exist behind a **Why?** or **Details** interaction.

---

# 4. The Core Fantasy

The child is not merely choosing combat units.

They are operating a futuristic **Chimera Creator lab** capable of discovering creatures that have never existed before.

The fiction is intentionally loose. We do not need to explain exactly whether these are genetically engineered organisms, holograms, simulations, or creatures generated from some advanced machine. The neon lab gives us a compelling visual world without forcing hard science onto the premise.

The fantasy should feel like:

**secret creature laboratory + monster encyclopedia + futuristic tournament arena.**

The player should feel:

- “I made this.”
- “Nobody else would have thought of this exact combination.”
- “I want to see what the next combination becomes.”
- “I want to know whether my favorite can become champion.”

---

# 5. Visual Direction

## Working aesthetic

The chosen visual direction is a **neon cyber creature lab**.

This is not the most naturalistic or literary version of the concept, but it is the direction the target child responded to most strongly, and that matters.

The style should use:

- deep navy and black environments;
- electric cyan and blue holographic lighting;
- purple as the signature creation/fusion color;
- teal for navigation and neutral systems;
- gold for tournaments, champions, and exceptional achievement;
- large holographic creature platforms;
- clean sci-fi panels and strong silhouettes;
- high-quality, cinematic creature rendering inside a simplified UI.

## Important tension: creature complexity vs. interface simplicity

The **creatures should remain visually sophisticated** even though the game systems are being simplified.

That distinction is important.

The seven-year-old does not need a simplified-looking monster. The appeal is that an absurd combination is rendered with seriousness and spectacle.

A creature can look like a AAA movie monster while its stat panel says only:

- Power: 95
- Speed: 85
- Armor: 90
- Size: 94

The art delivers depth. The interface delivers clarity.

## Visual north star

Every creature reveal should feel worthy of stopping and staring at.

The creature is always the star of the screen. The UI should frame it rather than compete with it.

---

# 6. The Chimera Rule

Every created chimera is built from **exactly four source creatures**.

The preferred rule remains:

1. **one mythical or fictional creature**;
2. **one extinct creature**;
3. **two living creatures**.

Examples:

- Dragon + Stegosaurus + Electric Eel + Shark → **Stormback Leviadrake**
- Basilisk + Megalodon + Lobster + Electric Eel → **Basilodion**
- Phoenix + Saber-Toothed Tiger + Walrus + Salmon → **Tideburn Aurion**

## Why four?

Four appears to be the sweet spot between simplicity and surprise.

Two animals can feel like a straightforward mash-up. Three often still produces an obvious hybrid. Four creates enough competing traits that the AI has to invent something genuinely new.

Four also gives the creation process a satisfying rhythm:

**1 → 2 → 3 → 4 → reveal.**

It is simple enough for a child to understand and structured enough to become an iconic interaction.

## Whether the category rule must be enforced

This remains an open product question.

Possible approaches:

### A. Strict mode
Every creation must use exactly one mythical, one extinct, and two living creatures.

**Pros:** reinforces the game's identity and produces varied inputs.  
**Cons:** adds conceptual friction for young players.

### B. Guided mode — recommended for MVP
The picker visually groups creatures and encourages the intended formula, but the child mostly experiences it as “pick four creatures.”

The system can guide selection with labels such as:

- Mythic
- Extinct
- Animal

without making the rule feel like homework.

### C. Free-build mode
Any four sources are allowed.

This could be an unlock or sandbox mode later.

---

# 7. Refined Core Game Loop

The first version should revolve around this loop:

## 1. MAKE

Choose four source creatures.

The player can deliberately choose each creature or use **Randomize**.

The interface previews what each selected ingredient contributes in very simple language.

Example:

- **Dragon** → horns, claws, fire
- **Stegosaurus** → armor plates
- **Electric Eel** → electricity
- **Shark** → bite and swimming

Then the player presses a large action such as:

**CREATE CHIMERA**

---

## 2. REVEAL

The game generates:

- the creature image;
- name;
- optional title;
- four source ingredients;
- a small set of core stats;
- 3–4 signature abilities;
- short strengths;
- short weaknesses;
- creature size/class;
- optional habitat/combat role;
- a richer internal description stored for future battle reasoning.

The reveal should be celebratory and paced.

Suggested sequence:

1. fusion chamber activates;
2. silhouette appears;
3. creature render resolves;
4. name appears;
5. rarity/style badge appears;
6. stats animate in;
7. abilities reveal;
8. buttons: **Add to Codex**, **Make Another**, **Enter Bracket**.

The player should have a reason to spend 10–20 seconds simply admiring the result.

---

## 3. COLLECT

Every created creature is added to the player's **Codex**.

The Codex is not merely storage. It is the long-term emotional record of everything the child has invented.

The player can browse and sort by fun questions:

- All
- Favorites
- Winners
- Biggest
- Fastest
- Strongest
- Newest
- Champions

This is preferable to expecting a child to configure advanced filters.

---

## 4. PREDICT

When two creatures meet in the arena, the primary child interaction is:

> **Who do you think will win?**

The player chooses one.

This is likely more age-appropriate and more aligned with the original “playground argument” than asking the child to operate a complex turn-based combat system.

Optionally, before locking the prediction, the game can show a few easy clues:

- battlefield type;
- creature size;
- key abilities;
- obvious strengths/weaknesses.

The child can make a gut choice or reason about the matchup.

---

## 5. SIMULATE

The AI evaluates the battle.

The winner should not be determined by one universal power score.

The simulation should consider:

- terrain/environment;
- creature size;
- mobility;
- speed;
- defense;
- attack options;
- range;
- supernatural powers;
- elemental interactions;
- weaknesses;
- stamina/endurance;
- specific ability synergies;
- whether one creature can realistically force the other into its preferred environment.

The result should be **deterministic enough to feel fair but variable enough that matchups remain interesting**. Exact implementation needs design/engineering discussion.

---

## 6. EXPLAIN

The game tells the player whether their prediction was correct.

Example:

**You picked Stormback Leviadrake.**  
**CORRECT!**

Then show **three simple reasons**:

- 🛡️ **Stronger Armor** — Basilodion struggled to break through.
- ⚡ **Electric Advantage** — Stormback's shocks were especially effective in the water.
- 🌊 **Fast Water Charge** — Stormback landed the first major hit.

A short optional cinematic narrative can be available underneath:

> “Basilodion charged through the surf, but Stormback's plated back absorbed the first bite. When the fight moved into deeper water, Stormback released a massive electric surge and drove Basilodion back.”

The top layer is understandable to a seven-year-old. The deeper layer preserves the richness of the original concept.

---

## 7. ADVANCE

The winning creature advances through the bracket.

Recommended initial bracket:

**8 creatures → quarterfinals → semifinals → championship.**

This is short enough to understand and long enough to create a meaningful champion.

The player continues predicting each battle.

---

## 8. CROWN

At the end of the bracket, one creature becomes **Champion**.

The winning creature receives a visible persistent accolade in the Codex.

Possible records:

- Tournament Champion
- 3-Time Champion
- Most Wins
- Biggest Upset
- Fastest Win

The final champion screen should feel like an event.

---

## 9. RETURN

The player returns to the Codex, where the tournament has changed the collection:

- win/loss records updated;
- champion badge added;
- top-winner rankings updated;
- favorites remain visible;
- new “best ever” records may have been set.

This gives battles persistence and makes the collection more interesting over time.

Then the obvious question becomes:

> “What should I create next?”

And the loop restarts.

---

# 8. Why Prediction Is Better Than Deep Tactical Combat for the First Version

A traditional monster battler would ask the player to choose attacks, manage energy, understand status effects, and optimize type relationships.

That can be fun, but it shifts the game away from its most original strengths.

The unique part of Chimera Creator is not that it can reproduce Pokémon combat.

The unique part is that the player can invent a creature the game designer never anticipated and then ask:

> **Would this thing beat that thing?**

Prediction preserves that fantasy.

It also has several advantages:

- easier for younger children;
- keeps battles fast;
- makes AI reasoning central rather than hidden;
- encourages discussion with parents/siblings/friends;
- makes surprising outcomes fun instead of frustrating;
- lets the child be “right” or “wrong” without losing control of a creature they carefully built;
- supports tournaments without requiring long combat sessions.

## Potential later expansion

A future **Tactics Mode** could allow older players to choose abilities or simple strategies.

But that should be additive, not required for the core product.

---

# 9. Battle Design

## Battle setup

Each matchup includes:

- Creature A
- Creature B
- an environment
- optionally one unusual battle condition

Example environments:

- Storm Coast
- Deep Ocean
- Volcanic Shore
- Jungle Canyon
- Frozen Ridge
- Open Sky
- Desert Ruins
- Swamp
- City Harbor

The environment is important because it prevents the game from collapsing into a static ranking of strongest to weakest.

A creature may dominate one opponent in the ocean but lose badly to the same opponent on dry land.

## Pre-battle screen

Show only information useful for a prediction:

### Creature A
- big portrait;
- name;
- 3–5 stat bars;
- 2 key strengths.

### Creature B
Same.

### Environment
Large visual card with 1–2 properties.

Example:

**STORM COAST**  
🌊 lots of water  
⚡ lightning storm

Then:

**WHO WILL WIN?**

Two giant choice buttons.

## Battle presentation

We do not necessarily need fully animated 3D combat in the MVP.

A strong first implementation could use:

- two high-quality generated creature images;
- environmental artwork;
- camera motion/parallax;
- particle effects;
- flashes, impacts, electricity, fire, water overlays;
- narrated text beats;
- health bars moving at key moments.

This can still feel cinematic while being feasible with generated assets.

## Battle narrative structure

Internally, the AI can generate a richer battle with:

1. opening;
2. first advantage;
3. counter;
4. turning point;
5. finisher;
6. winner.

The child-facing presentation may collapse this into 3–4 short beats.

---

# 10. Creature Generation System

The AI should not simply average four animals together.

Its job is to invent **one coherent fictional species**.

## Generation reasoning steps

For each of the four source creatures, identify:

- iconic appearance;
- signature weapon/adaptation;
- movement style;
- defensive trait;
- behavioral trait;
- supernatural/mythic power if relevant.

Then assign those traits to body systems.

Example:

**Basilisk + Megalodon + Lobster + Electric Eel**

- Basilisk → head, eyes, venom
- Megalodon → body scale, jaws, predatory movement
- Lobster → armor and crushing forelimbs
- Electric Eel → electric organs and tail

The creature must look like **one species**, not four animals stitched together.

## Synergy requirement

The best abilities should combine ingredients.

Example:

Shark + Electric Eel → **Thunder Bite**

not merely:

- Shark Bite
- Electric Shock

This makes the output feel invented rather than assembled.

## Weakness requirement

Every generated creature needs meaningful weaknesses.

The system should explicitly resist “everything is awesome at everything.”

Examples:

- very heavy armor → slower turning;
- flight + massive body → high energy consumption;
- deep-sea specialization → weaker on land;
- fire powers → reduced effectiveness in deep water;
- extreme speed → lower armor.

These weaknesses are essential for believable battle outcomes.

---

# 11. Naming

Every creature gets:

## Primary species name

Example:

**Stormback Leviadrake**

## Optional title

Example:

**The Thundered Leviathan**

Names should:

- sound exciting;
- be pronounceable by a child;
- avoid overly long fantasy gibberish;
- hint at one or two component traits;
- feel like they belong in the same universe.

The name itself is a major part of the reveal moment.

## Naming retry

The player should be able to request a new name without regenerating the entire creature.

Potential control:

**TRY ANOTHER NAME**

This is likely more useful than deep cosmetic editing in an MVP.

---

# 12. Stats: Simplified Child-Facing Model

The original concept allowed many biologically interesting measurements. We should preserve those internally, but simplify the main game UI.

## Core visible stats

Recommended default set:

- **Power**
- **Speed**
- **Armor**
- **Size**
- **Special** (or a creature-specific fifth stat)

Alternative fifth stats depending on creature:

- Bite
- Flight
- Electricity
- Fire
- Venom
- Stealth
- Endurance

This lets each creature feel different without requiring every creature to fit the exact same template.

## Internal stats

The simulation can retain richer hidden or expandable attributes such as:

- land speed;
- swim speed;
- flight speed;
- bite force;
- armor;
- intelligence;
- endurance;
- regeneration;
- range;
- maneuverability;
- elemental resistance;
- environmental suitability.

These can be exposed on a **Details** page for curious older users.

## Numbers vs. categories

The interface may use a 0–100 scale because children understand “95 is bigger than 80.”

However, battles must **not** simply add these numbers together to choose a winner.

---

# 13. Abilities

Each creature should have roughly **3–4 primary named abilities** in the child-facing interface.

Internally, more traits can exist.

Each ability should include:

- a strong icon;
- a short name;
- one short description.

Example:

### Thunder Surge
**Huge electric shock.**

### Spike Wall
**Raises armored back plates to block attacks.**

### Deep Sea Charge
**Rushes forward incredibly fast underwater.**

### Tidal Smash
**Creates a powerful wall of water.**

Abilities should connect visibly back to source creatures.

---

# 14. Codex / Creature Archive

The Codex is one of the most important systems in the game.

Creation produces a moment of excitement. The Codex turns those moments into long-term ownership.

## Card contents

Each creature card should show:

- hero thumbnail;
- name;
- optional rarity;
- number of wins or champion trophies;
- favorite marker.

Do not overload collection cards with full stats.

## Selected creature panel

When selected, show:

- larger image;
- name;
- four source creatures;
- core stats;
- wins / losses;
- win rate;
- champion badges;
- one or two fun records.

Examples:

- Biggest Win
- Fastest Win
- 3-Time Champion
- Largest Creature
- Most Powerful Bite

## Sorting should feel like questions

Prefer:

- Winners
- Biggest
- Fastest
- Newest
- Favorites

rather than spreadsheet-like sort configuration.

## Comparison

A dedicated two-creature comparison can exist, but it is secondary to the MVP loop.

If included, it should be visual and simple.

---

# 15. Tournament / Bracket Mode

## Default tournament

Use **8 selected chimeras**.

If the player has fewer than eight, allow AI-generated guest creatures or a smaller bracket.

The player can:

- manually choose entrants;
- press **Random Tournament**;
- choose favorites;
- eventually create themed tournaments.

## Each matchup

1. show environment;
2. show both creatures;
3. ask player to predict winner;
4. simulate;
5. explain result;
6. advance winner.

## Why brackets work

Brackets create a story with almost no rules explanation.

A seven-year-old intuitively understands:

> winner keeps going.

They also create suspense and allow a favorite creature to develop a narrative during a session.

## Championship

The final should receive more ceremony:

- gold visual treatment;
- bigger arena;
- trophy animation;
- persistent champion badge;
- Hall of Champions entry.

---

# 16. Hall of Champions

This should be a simple, highly celebratory screen.

Possible sections:

- Current Champion
- Most Tournament Wins
- Biggest Creature
- Fastest Creature
- Strongest Bite
- Most Surprising Champion
- Player's Favorite

This creates reasons to return to old creations.

It also turns generated creatures into characters with history rather than disposable AI outputs.

---

# 17. Proposed Primary Screens

These are the five screens currently defining the game direction.

## Screen 1 — Home / Welcome

Purpose: orient the child immediately.

Primary actions:

- **Create Chimera**
- **My Codex**
- **Battle Bracket**
- **Hall of Champions**

Supporting content:

- one featured chimera on the holographic platform;
- Today’s Crew / Favorites;
- simple Quick Stats;
- player name/avatar.

The player should be able to decide what to do within seconds.

---

## Screen 2 — Fusion Lab / Ingredient Selection

Purpose: make choosing four source creatures fun.

UI:

- four large slots;
- clear step indicator: **2 of 4 chosen**;
- large creature cards;
- short contribution labels;
- partial holographic preview;
- Randomize;
- Next Step.

Avoid requiring text search as the default interaction for a seven-year-old. Browsing should be visual.

Search can still exist for older players.

---

## Screen 3 — Creation Reveal

Purpose: maximize delight and ownership.

UI:

- huge creature render;
- generated name;
- source creatures;
- 4–5 stats;
- 3–4 abilities;
- “Top Facts”;
- Add to Codex;
- Make Another;
- Enter Bracket.

This is one of the two most important screens in the game.

---

## Screen 4 — Codex

Purpose: make past creations worth revisiting.

UI:

- visual collection grid;
- simple filters;
- selected creature details;
- wins/losses;
- fun records;
- Top Winners;
- Compare;
- Go to Arena.

---

## Screen 5 — Battle Result / Tournament Progress

Purpose: create suspense, teach why a matchup resolved the way it did, and move the tournament forward.

UI:

- both creature images;
- player's prediction;
- correct / incorrect result;
- winner;
- three reasons why;
- simplified health/result visualization;
- bracket progress;
- champion tracker;
- Next Battle.

The pre-battle prediction screen should be designed as a companion screen even if it is not counted among the five core direction mocks.

---

# 18. AI Responsibilities

AI is not an add-on to this game. It is the content engine.

We should assume AI can be used dynamically for:

- source-creature interpretation;
- coherent anatomy planning;
- creature naming;
- title generation;
- creature description;
- ability generation;
- strengths and weaknesses;
- core and hidden stats;
- habitat/environment affinity;
- combat archetype;
- creature image generation;
- thumbnail generation/cropping;
- matchup reasoning;
- battle narrative;
- short child-facing result explanation;
- optional deeper explanation;
- tournament guest creatures.

## Strong recommendation: generate structured data first

The creature should not exist only as prose plus an image.

The AI should produce a structured creature record that can be saved and reused.

Conceptual example:

```json
{
  "name": "Stormback Leviadrake",
  "title": "The Thundered Leviathan",
  "sources": [
    "Dragon",
    "Stegosaurus",
    "Electric Eel",
    "Shark"
  ],
  "role": "Bruiser / Area Control",
  "core_stats": {
    "power": 95,
    "speed": 85,
    "armor": 90,
    "size": 94,
    "bite": 92
  },
  "abilities": [],
  "strengths": [],
  "weaknesses": [],
  "environment_affinities": [],
  "combat_profile": {},
  "visual_spec": {},
  "image_asset": "..."
}
```

The exact schema should be designed by engineering and game design together.

## Separate player-facing and simulation-facing data

This is important.

The child might see:

**FAST IN WATER**

while the internal simulation record contains a much richer representation of aquatic mobility, maneuverability, terrain dependence, and attack range.

That allows the game to stay simple without making battle reasoning shallow.

---

# 19. AI Creature Image Pipeline

## Input

- four source creatures;
- anatomy plan;
- signature abilities;
- habitat;
- size;
- visual identity;
- optional style seed / consistency guidance.

## Output

At minimum:

- primary hero image;
- transparent or clean-background creature render if feasible;
- thumbnail/crop variants.

## Art rules

The image should:

- depict one coherent creature;
- visibly incorporate all four source creatures;
- prioritize a dramatic readable silhouette;
- treat the premise seriously;
- avoid accidental extra heads/limbs unless intentional;
- match the chosen neon-lab presentation without requiring the creature itself to be neon-colored;
- preserve creature identity across Codex and battle contexts where practical.

## Open challenge: identity consistency

If the same creature must appear repeatedly in different poses and scenes, image-generation consistency becomes a meaningful technical/product problem.

Possible approaches should be investigated early:

- reuse the original hero render extensively;
- create battle scenes through compositing rather than complete regeneration;
- store detailed visual descriptors;
- generate several canonical assets during initial creation;
- later use stronger image-conditioning workflows if available.

This is a major implementation question, not a minor art detail.

---

# 20. AI Battle Engine

The battle engine should answer:

> **Given these two specific creatures and this environment, what probably happens?**

It should not answer:

> Which creature has the larger total stat number?

## Recommended conceptual flow

### Step 1: load both saved creature profiles

No re-invention of established stats or abilities during battle.

### Step 2: load environment

Example:

- water depth;
- terrain;
- airspace;
- temperature;
- cover;
- hazards.

### Step 3: evaluate matchup dimensions

- mobility;
- offensive reach;
- defense;
- likely opening behavior;
- specific counters;
- environmental fit;
- stamina;
- exploitable weaknesses.

### Step 4: produce an internal battle result

This should include:

- winner;
- confidence;
- decisive interactions;
- major battle beats;
- optional remaining health abstraction.

### Step 5: produce child-facing explanation

Exactly 2–3 main reasons.

### Step 6: produce optional narrative

Short dramatic battle story.

## Randomness / repeatability

We need a design decision on whether the exact same matchup in the exact same environment always produces the same winner.

Possible direction:

- use a stable expected advantage;
- allow controlled variance;
- make stronger matchup advantages win more often, not necessarily always.

For a child, pure unpredictability may feel unfair, while perfect determinism may reduce replayability.

This needs testing.

---

# 21. Rarity and Progression

Rarity is visually appealing but should not imply that the game secretly favors some combinations regardless of matchup.

Potential labels:

- Uncommon
- Rare
- Epic
- Legendary

However, rarity should probably describe **how unusual/impressive the generated creature is**, not function as a direct battle multiplier.

Otherwise the child quickly learns that “Legendary always wins,” which undermines matchup debate.

## Player progression

MVP progression should be light.

Potential progression rewards:

- player level;
- new source creatures unlocked;
- new environments;
- new lab themes;
- additional Codex slots if we even need limits;
- cosmetic badges;
- tournament trophies.

Avoid complex equipment or upgrade economies initially.

---

# 22. Source Creature Library

The game needs a curated source-creature library even though the resulting chimeras are generated dynamically.

Each source should have a stable metadata record including:

- name;
- category: mythic / extinct / living / fictional;
- image/icon;
- simple child-facing traits;
- richer AI-facing traits;
- common powers/adaptations;
- habitat;
- scale;
- movement type;
- tags.

This gives generation consistency and reduces the likelihood that AI interprets the same source radically differently each time.

## Initial library size

Open question.

A useful MVP might have enough animals for combinations to feel effectively endless without creating an overwhelming picker.

Possible starting range:

- 15–25 mythical/fictional;
- 20–30 extinct;
- 40–60 living animals.

The exact number should be tested against picker usability and content-preparation cost.

---

# 23. Safety and Child Appropriateness

The game involves creatures fighting, biting, claws, venom, fire, and other potentially violent concepts.

The tone should be **epic monster action**, not gore.

Avoid:

- blood-heavy imagery;
- dismemberment;
- suffering-focused descriptions;
- graphic death language.

Prefer:

- defeated;
- knocked out;
- driven back;
- overwhelmed;
- forced to retreat;
- arena victory.

Generated names, descriptions, images, and battle text should be constrained to the intended age range.

This should be treated as part of the AI generation contract, not left to chance.

---

# 24. Multiplayer / Social Scope

Not required for MVP.

The “playground argument” can exist even in a local single-player game.

Natural later features include:

- parent/child shared Codex;
- sibling tournaments;
- share a creature card;
- challenge a friend's saved chimera;
- local “whose creature wins?” mode.

If online sharing is added, child safety and moderation implications become much larger and should be addressed as a separate product initiative.

---

# 25. MVP Proposal

A strong MVP can be significantly smaller than a traditional creature battler.

## Must have

### Creation
- curated source creature library;
- four-part selection flow;
- AI creature generation;
- generated hero image;
- name;
- stats;
- 3–4 abilities;
- strengths/weaknesses;
- save to Codex.

### Codex
- creature grid;
- creature details;
- favorites;
- wins/losses;
- sort by a few fun dimensions.

### Tournament
- 8-creature bracket;
- environment per battle;
- player prediction;
- AI battle result;
- 3-reason explanation;
- bracket advancement;
- champion.

### History
- persistent battle records;
- champion badge;
- Top Winners.

### Visual
- coherent neon-lab design system;
- consistent reusable hero creature presentation;
- strong reveal moment.

## Explicitly not required for MVP

- real-time combat;
- deep tactical ability selection;
- equipment;
- breeding;
- crafting;
- multiplayer matchmaking;
- trading;
- open chat;
- complicated economy;
- huge progression tree;
- fully animated 3D creatures.

---

# 26. Suggested MVP Session

A representative first session should look like this:

### Minute 0
Player lands on Home and presses **Create Chimera**.

### Minute 1
Player picks:

- Dragon
- Stegosaurus
- Electric Eel
- Shark

### Minute 2
Fusion begins.

### Minute 3
**Stormback Leviadrake** is revealed.

Player admires it, reads abilities, and adds it to Codex.

### Minute 4–10
Player makes several more creatures.

### Minute 11
Player opens **Battle Bracket** and selects eight creatures.

### Minutes 12–18
For each matchup:

- player predicts;
- battle sim resolves;
- player sees whether they were correct;
- winner advances.

### Minute 19
Championship.

### Minute 20
Champion ceremony.

### Minute 21
Player returns to Codex and sees:

- champion badge;
- updated wins;
- Top Winners.

Likely next action:

> Create a creature designed to beat the champion.

That is an excellent retention loop.

---

# 27. Product Principles / Decision Tests

When the team debates a feature, use these tests.

## Does it make creation more exciting?

If yes, likely valuable.

## Does it make the creature feel more personally owned?

If yes, likely valuable.

## Does it make “who would win?” more interesting?

If yes, likely valuable.

## Does a seven-year-old understand what to do next?

If no, simplify.

## Does it require the player to understand hidden simulation complexity?

If yes, hide or translate the complexity.

## Does it cause the UI to compete with the creature art?

If yes, reduce it.

## Does it make every creature converge toward a generic power ranking?

If yes, rethink it.

## Does it create a reason to care about a creature after the reveal?

If no, it may be disposable AI novelty rather than game design.

---

# 28. Important Open Questions for Team Discussion

This document intentionally does not resolve everything. These are the questions the team should push on.

## Creation

1. Is mythical + extinct + living + living a hard rule or guided recommendation?
2. Can duplicate source creatures be used?
3. Can the player reroll only the name? Stats? Image? Entire creature?
4. Does rerolling create a new creature or revise the existing one?
5. How much control should players have over the final anatomy?
6. How long is an acceptable AI generation wait for a seven-year-old?
7. What do we show while image generation is happening?

## Creature identity

8. How do we maintain the same creature's appearance across hero image, Codex thumbnail, and battle?
9. Do creatures ever evolve/change visually?
10. Are stats immutable once generated?
11. How do we prevent obviously nonsensical or broken AI outputs from entering the permanent Codex?

## Battle

12. Is the battle winner deterministic for a matchup/environment or probabilistic?
13. How much randomness feels exciting versus unfair?
14. Does the player ever choose an ability, or only predict?
15. Do environments come from a curated set or can AI generate new ones?
16. How do we communicate an upset without making the simulation feel arbitrary?
17. Can the same two creatures rematch in a different environment?
18. What happens on a very close matchup?

## Tournament

19. Are brackets always eight creatures?
20. Who selects entrants?
21. Can the game auto-fill with guest creatures?
22. Does the child predict every matchup, including matches not involving a favorite?
23. What persistent reward does a champion receive?

## Codex

24. Is there a limit to the number of saved creatures?
25. How do we make hundreds of creations browsable by a young child?
26. Which superlatives should we track?
27. Should the game show a universal “Power” ranking if matchups are supposed to be contextual?

## AI / cost / latency

28. What parts of creation can be generated in parallel?
29. What should be cached forever once a creature is created?
30. How much does each creation cost at target usage?
31. Should a creature be fully generated in one AI job or staged across multiple calls?
32. What happens when an image/text generation fails?
33. How do we enforce schema consistency over time?

## Safety

34. What generated creature combinations should be rejected or softened?
35. What level of monster violence is acceptable in imagery and narration?
36. If sharing is added later, what parental and moderation systems are required?

---

# 29. Longer-Term Possibilities

These are deliberately outside the MVP, but the architecture should not unnecessarily block them.

## Challenge Mode

“Create a chimera that can beat the current champion.”

This may be one of the strongest future modes because it directly links creation and battle strategy.

## Themed tournaments

- Ocean Monsters Only
- Flyers Cup
- Tiny Titans
- Fire vs. Ice
- Mythic Madness

## Simple tactics mode

Before simulation, choose one plan:

- Attack Fast
- Defend First
- Keep Distance
- Use the Environment

This could provide more agency without becoming a traditional RPG.

## Creature quests

A favorite creature could earn titles by completing challenges.

## Parent/child co-play

Each person creates four creatures, then runs a shared bracket.

## Creature cards / export

Create a shareable visual card for each chimera.

## Seasonal records

Hall of Champions can preserve tournament history over time.

---

# 30. The Design North Star

Chimera Creator should not feel like a spreadsheet wearing monster art.

It should not feel like a generic battle game where AI happens to generate the characters.

The AI-generated creature itself is the magic trick.

The game exists to give that magic trick **meaning and memory**.

Creation creates curiosity.

The reveal creates attachment.

The Codex creates ownership.

Prediction creates participation.

The battle explanation creates the argument.

The bracket creates a story.

The champion creates history.

Then the player creates another creature because now there is something to beat.

## Final product loop

> **CREATE → REVEAL → COLLECT → PREDICT → SIMULATE → EXPLAIN → ADVANCE → CROWN → CREATE AGAIN**

If those moments are excellent, the game does not need dozens of additional systems.

The core promise remains very simple:

> **Pick four creatures. Invent something nobody has ever seen. Then find out if it can become champion.**
