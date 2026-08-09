/* The Fusion Wait — the 30-75s the chimera takes to cook, staged as theatre
   rather than a spinner (ARCHITECTURE.md: staged reveal; brief: never a bare
   spinner).

   Phase A  IGNITION    the four chosen portraits fly into the chamber and orbit
   Phase B  SPLICING    name slams in; while the genome streams, the center
                        stage spotlights each source creature in turn — the
                        portrait enlarges toward center over the vortex with a
                        holo plate of what it contributes
   Phase C  WALKTHROUGH once the record completes and the hero still paints,
                        the ability walkthrough takes over the spotlight

   The right panel is a CODEX PREVIEW — the same visual language as the codex
   detail panel, filling in chunk by chunk as the record streams: name slams
   in, title/rarity land, stat bars animate, move chips glow on one by one,
   strengths/weaknesses chips arrive, and RENDER INCOMING marks where the hero
   will land. Big type; this is the primary progressive-disclosure surface.

   Every progress milestone is real: the conduit fills off record_status /
   ability_names / core_stats / image_started / image_status, never off a bare
   timer. BODY FORGE ignites on the backend's image_started signal and then
   crawls asymptotically toward 90 — honest start, theatrical middle. */
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import type { Ability, CreatureDetail, SourceCreature } from "./api";
import { getLibraryCached } from "./api";
import { Asset, Badge, FitText, Meter, PartImg, RarityBadge, cleanList } from "./ui";

/* -- picks handoff ----------------------------------------------------------
   FusionLab -> Reveal goes through a hash change, so the chosen four would be
   lost. Stashing them means the portraits are on screen in the same frame the
   chamber opens; creature.sources from the API is the fallback. */
let stashed: { id: number; picks: SourceCreature[] } | null = null;

export function stashPicks(id: number, picks: SourceCreature[]): void {
  stashed = { id, picks };
}

function readPicks(id: number): SourceCreature[] | null {
  return stashed && stashed.id === id ? stashed.picks : null;
}

const VERBS = [
  "Splicing",
  "Charging",
  "Weaving",
  "Grafting",
  "Stabilising",
  "Encoding",
  "Calibrating",
  "Fusing",
];
const LINE_MS = 2500;
const SPARKS = 18;
/** Source-creature spotlight cadence while the genome streams. */
const SRC_MS = 4600;
/** Auto-tour cadence through the ability walkthrough. */
const TOUR_MS = 6000;
/** How long a tap holds the spotlight before the tour resumes. */
const TOUR_RESUME_MS = 24000;

const STAT_KEYS = ["power", "speed", "armor", "size", "special"] as const;
const STAT_TONES: Record<string, string> = {
  power: "purple",
  speed: "cyan",
  armor: "green",
  size: "gold",
  special: "orange",
};

type StageState = "done" | "active" | "waiting";

/** One stop on the ability walkthrough tour. */
type TourItem =
  | { kind: "ability"; ability: Ability; index: number }
  | { kind: "strength"; text: string }
  | { kind: "weakness"; text: string };

/** Resolve an ability's fused-from names (or slugs) to library entries so the
    walkthrough can show their real portraits — including a summoned part's
    /media portrait (PartImg owns that), never a gap marker mid-theatre. */
function matchSources(names: string[], pool: SourceCreature[]): SourceCreature[] {
  const canon = (s: string) => s.trim().toLowerCase().replace(/[\s_-]+/g, " ");
  return names
    .map((raw) => {
      const key = canon(raw);
      return pool.find((s) => canon(s.slug) === key || canon(s.name) === key);
    })
    .filter((s): s is SourceCreature => Boolean(s));
}

export function FusionWait({
  creature,
  creatureId,
  heroReady,
}: {
  creature: CreatureDetail | null;
  creatureId: number;
  /** True once the finished hero PNG has decoded in the browser. */
  heroReady: boolean;
}) {
  const [sources, setSources] = useState<SourceCreature[]>(
    () => readPicks(creatureId) ?? [],
  );
  const [line, setLine] = useState(0);
  const [statsIn, setStatsIn] = useState(false);

  const recordDone = creature?.record_status === "complete";
  const imageDone = creature?.image_status === "complete";
  const slugKey = (creature?.sources ?? readPicks(creatureId)?.map((s) => s.slug) ?? []).join(",");

  /* Resolve the four sources to full library entries (portrait + contributes).
     The stash usually wins; this covers a reload straight onto #/reveal/<id>. */
  useEffect(() => {
    if (!slugKey) return;
    let dead = false;
    getLibraryCached()
      .then((lib) => {
        if (dead) return;
        const byslug = new Map(lib.sources.map((s) => [s.slug, s]));
        const resolved = slugKey.split(",").map((slug) => byslug.get(slug)).filter(Boolean);
        if (resolved.length) setSources(resolved as SourceCreature[]);
      })
      .catch(() => undefined);
    return () => {
      dead = true;
    };
  }, [slugKey]);

  const lines = useMemo(() => buildLines(sources), [sources]);

  useEffect(() => {
    if (lines.length < 2) return;
    const t = setInterval(() => setLine((i) => (i + 1) % lines.length), LINE_MS);
    return () => clearInterval(t);
  }, [lines.length]);

  const stats = creature?.core_stats ?? {};
  const hasStats = typeof stats.power === "number";
  const abilityNames = creature?.ability_names?.length
    ? creature.ability_names
    : (creature?.abilities ?? []).map((a) => a.name);

  /* Bars are mounted empty for one frame so the fill reads as a fill. */
  useEffect(() => {
    if (!hasStats) return;
    const t = setTimeout(() => setStatsIn(true), 60);
    return () => clearTimeout(t);
  }, [hasStats]);

  /* -- ability walkthrough (record done, hero still painting) -------------- */
  const abilities = creature?.abilities ?? [];
  const walkthroughOn = recordDone && !heroReady && abilities.length > 0;
  const strengths = useMemo(() => cleanList(creature?.strengths ?? []), [creature?.strengths]);
  const weaknesses = useMemo(() => cleanList(creature?.weaknesses ?? []), [creature?.weaknesses]);

  const tour: TourItem[] = useMemo(() => {
    if (!walkthroughOn) return [];
    return [
      ...abilities.map((ability, index): TourItem => ({ kind: "ability", ability, index })),
      ...strengths.map((text): TourItem => ({ kind: "strength", text })),
      ...weaknesses.map((text): TourItem => ({ kind: "weakness", text })),
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed by content lengths
  }, [walkthroughOn, abilities.length, strengths.length, weaknesses.length]);

  const [tourIx, setTourIx] = useState(0);
  const [tapHeld, setTapHeld] = useState(false);

  /* Auto-tour: the spotlight advances on its own so a kid who just watches
     still gets the whole walkthrough. */
  useEffect(() => {
    if (tour.length < 2 || tapHeld) return;
    const t = setInterval(() => setTourIx((i) => (i + 1) % tour.length), TOUR_MS);
    return () => clearInterval(t);
  }, [tour.length, tapHeld]);

  /* A tap holds the spotlight, then the tour quietly resumes. */
  useEffect(() => {
    if (!tapHeld) return;
    const t = setTimeout(() => setTapHeld(false), TOUR_RESUME_MS);
    return () => clearTimeout(t);
  }, [tapHeld, tourIx]);

  const spot: TourItem | null = tour.length ? tour[tourIx % tour.length] : null;
  const spotSources =
    spot?.kind === "ability" ? matchSources(spot.ability.sources, sources) : [];

  /* -- source spotlight: one donor at a time while the genome streams ------- */
  const [srcIx, setSrcIx] = useState(0);
  const spotlightSources = !walkthroughOn && sources.length > 0;
  useEffect(() => {
    if (!spotlightSources || sources.length < 2) return;
    const t = setInterval(() => setSrcIx((i) => (i + 1) % sources.length), SRC_MS);
    return () => clearInterval(t);
  }, [spotlightSources, sources.length]);
  const srcSpot = spotlightSources ? sources[srcIx % sources.length] : null;

  /* -- conduit: BODY FORGE ignites on the backend's image_started signal ---- */
  const imageStarted = Boolean(creature?.image_started) || imageDone;
  const [forge, setForge] = useState(0);
  useEffect(() => {
    if (!imageStarted || imageDone) {
      if (!imageStarted) setForge(0);
      return;
    }
    const t0 = Date.now();
    const tick = () =>
      setForge((prev) => {
        const s = (Date.now() - t0) / 1000;
        return Math.max(prev, Math.min(90, Math.round(90 * (1 - Math.exp(-s / 28)))));
      });
    tick();
    const t = setInterval(tick, 700);
    return () => clearInterval(t);
  }, [imageStarted, imageDone]);

  const conduit = conduitStages(creature, heroReady, imageStarted, forge);
  /* Conduit labels carry the state; the status line speaks only for the two
     download moments (the old footer chatter is gone). */
  const status = heroReady ? "RENDER COMPLETE" : imageDone ? "DOWNLOADING THE FINISHED RENDER" : null;

  return (
    <div className="fw">
      <header className="fw__head">
        <p className="eyebrow">FUSION CHAMBER ONLINE</p>
        <h1 className="display">SPLICING YOUR CHIMERA</h1>
      </header>

      <div className="fw__main">
        <section className="fw__rail">
          <div className="fw__ticker" key={lines[line] ?? "boot"}>
            <span className="fw__ticker-text">
              {lines.length ? lines[line] : "Warming the splice coils..."}
            </span>
          </div>

          <div className="panel panel--teal fw__panel">
            <header className="panel__head">
              <h2>CORE STATS</h2>
              {hasStats && <Badge tone="green">LOCKED IN</Badge>}
            </header>
            <div className="panel__body fw__stats">
              {STAT_KEYS.map((key, i) => {
                const value = (stats as Record<string, number | string>)[key];
                const known = typeof value === "number";
                return (
                  <div
                    className={`fw__stat${known ? " is-in" : ""}`}
                    key={key}
                    style={{ animationDelay: `${i * 90}ms` }}
                  >
                    <Asset slot={`icons/stat_${key}`} label={key} className="fw__stat-icon" />
                    <span className="fw__stat-name">
                      {key === "special" ? stats.special_name || "SPECIAL" : key}
                    </span>
                    <Meter
                      value={known && statsIn ? (value as number) : 0}
                      tone={STAT_TONES[key]}
                    />
                    <span className="fw__stat-value num">{known ? value : "--"}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="panel panel--purple fw__panel">
            <header className="panel__head">
              <h2>ABILITIES</h2>
              <span className="num muted">
                {recordDone ? `${abilities.length} DECODED` : "DECODING"}
              </span>
            </header>
            <div className="panel__body">
              <div className="fw__chips">
                {walkthroughOn
                  ? abilities.map((a, i) => (
                      <button
                        type="button"
                        className={`fw__chip fw__chip--live${
                          spot?.kind === "ability" && spot.index === i ? " is-spot" : ""
                        }`}
                        key={a.name}
                        onClick={() => {
                          setTourIx(i);
                          setTapHeld(true);
                        }}
                      >
                        {a.name.toUpperCase()}
                      </button>
                    ))
                  : abilityNames.map((name) => (
                      <span className="fw__chip" key={name}>
                        {name.toUpperCase()}
                      </span>
                    ))}
                {/* Unstreamed slots are a deliberate mystery, never an empty box:
                    the specimen may carry up to four abilities. */}
                {!recordDone &&
                  Array.from({ length: Math.max(0, 4 - abilityNames.length) }).map((_, i) => (
                    <span className="fw__chip fw__chip--mystery" key={`mystery${i}`} aria-hidden="true">
                      ?
                    </span>
                  ))}
              </div>
            </div>
          </div>
        </section>

        <section className="fw__chamber">
          <div className="fw__chamber-art">
            <Asset slot="lab/fusion_chamber" label="" className="fw__chamber-img" />
            <div className="fw__sparks" aria-hidden="true">
              {Array.from({ length: SPARKS }).map((_, i) => (
                <span
                  key={i}
                  style={
                    {
                      "--x": `${(i * 37) % 100}%`,
                      "--delay": `${(i * 0.31) % 3.4}s`,
                      "--dur": `${2.2 + ((i * 7) % 18) / 10}s`,
                      "--drift": `${((i % 5) - 2) * 14}px`,
                    } as CSSProperties
                  }
                />
              ))}
            </div>
            <div className="fw__orbits">
              {sources.map((s, i) => (
                <div
                  className="fw__orbiter"
                  key={s.slug}
                  style={
                    {
                      "--a": `${i * 90}deg`,
                      "--delay": `${i * 0.16}s`,
                    } as CSSProperties
                  }
                >
                  <div className="fw__orbiter-inner">
                    <div className="fw__orbiter-art">
                      <PartImg source={s} />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Source spotlight: the donor's portrait enlarges toward center
                over the vortex with a holo plate of what it contributes. */}
            {srcSpot && (
              <div className="fw__srcspot" key={srcSpot.slug}>
                <span className="fw__srcspot-art">
                  <PartImg source={srcSpot} />
                </span>
                <div className="fw__srcspot-plate">
                  <FitText className="fw__srcspot-name">{srcSpot.name.toUpperCase()}</FitText>
                  <p className="fw__srcspot-line">{contributionOf(srcSpot)}</p>
                </div>
              </div>
            )}
          </div>

          <div className="fw__name-slot">
            {creature?.name ? (
              <div className="fw__named" key={creature.name}>
                <span className="fw__flashline" aria-hidden="true" />
                <h2 className="fw__name">{creature.name.toUpperCase()}</h2>
                {creature.title && <p className="fw__title">{creature.title}</p>}
                {creature.rarity && <RarityBadge rarity={creature.rarity} />}
              </div>
            ) : (
              <div className="fw__unnamed">
                <span className="fw__dots">
                  <i />
                  <i />
                  <i />
                </span>
                NAMING THE SPECIMEN
              </div>
            )}
          </div>

          {/* Ability walkthrough spotlight — center stage while the hero paints. */}
          {walkthroughOn && spot && (
            <div className="fw__spot" key={`${spot.kind}${"index" in spot ? spot.index : spot.text}`}>
              {spot.kind === "ability" ? (
                <>
                  <span className="fw__spot-key">
                    ABILITY {spot.index + 1} OF {abilities.length}
                  </span>
                  <h3 className="fw__spot-name">{spot.ability.name.toUpperCase()}</h3>
                  <p className="fw__spot-blurb">{spot.ability.blurb}</p>
                  {spotSources.length > 0 && (
                    <div className="fw__spot-sources">
                      <span className="fw__spot-fused">FUSED FROM</span>
                      {spotSources.map((s) => (
                        <span className="fw__spot-src" key={s.slug} title={s.name}>
                          <PartImg source={s} />
                        </span>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <>
                  <span className="fw__spot-key">
                    {spot.kind === "strength" ? "STRONG AT" : "WATCH OUT"}
                  </span>
                  <p className="fw__spot-blurb">{spot.text}</p>
                </>
              )}
              <span className="fw__spot-hint">
                {tapHeld ? "HOLDING HERE — THE TOUR RESUMES SOON" : "TAP AN ABILITY TO LOOK CLOSER"}
              </span>
            </div>
          )}
        </section>

        {/* CODEX PREVIEW — the record forming as a codex card, chunk by chunk. */}
        <section className="fw__rail">
          <div className="panel panel--purple fw__panel fw__preview">
            <header className="panel__head">
              <h2>CODEX PREVIEW</h2>
              {recordDone && <Badge tone="green">COMPLETE</Badge>}
            </header>
            <div className="panel__body fw__pv">
              {creature?.name ? (
                <div className="fw__pv-name" key={creature.name}>
                  <FitText>{creature.name.toUpperCase()}</FitText>
                </div>
              ) : (
                <div className="fw__pv-waitline">
                  <span className="fw__dots">
                    <i />
                    <i />
                    <i />
                  </span>
                  READING THE GENOME
                </div>
              )}

              {(creature?.title || creature?.rarity) && (
                <div className="fw__pv-sub">
                  {creature?.rarity && <RarityBadge rarity={creature.rarity} />}
                  {creature?.title && <span className="fw__pv-title">{creature.title}</span>}
                </div>
              )}

              <div className="fw__pv-stats">
                {STAT_KEYS.map((key) => {
                  const value = (stats as Record<string, number | string>)[key];
                  const known = typeof value === "number";
                  return (
                    <div className={`fw__pv-stat${known ? " is-in" : ""}`} key={key}>
                      <span className="fw__pv-statname">
                        {key === "special" ? stats.special_name || "SPECIAL" : key}
                      </span>
                      <Meter value={known && statsIn ? (value as number) : 0} tone={STAT_TONES[key]} />
                    </div>
                  );
                })}
              </div>

              {abilityNames.length > 0 && (
                <div className="fw__pv-chips">
                  {abilityNames.map((name) => (
                    <span className="chip chip--purple is-lit" key={name}>
                      {name.toUpperCase()}
                    </span>
                  ))}
                </div>
              )}

              {(strengths.length > 0 || weaknesses.length > 0) && (
                <div className="fw__pv-traits">
                  {strengths.length > 0 && (
                    <div className="traits__row">
                      <span className="traits__key traits__key--green">STRONG AT</span>
                      {strengths.slice(0, 2).map((text) => (
                        <span className="chip chip--green is-lit" key={text}>
                          {text.split(/\s+/).slice(0, 3).join(" ").replace(/[.,;:!?'"]+$/, "").toUpperCase()}
                        </span>
                      ))}
                    </div>
                  )}
                  {weaknesses.length > 0 && (
                    <div className="traits__row">
                      <span className="traits__key traits__key--red">WATCH OUT</span>
                      {weaknesses.slice(0, 2).map((text) => (
                        <span className="chip chip--red is-lit" key={text}>
                          {text.split(/\s+/).slice(0, 3).join(" ").replace(/[.,;:!?'"]+$/, "").toUpperCase()}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className={`fw__pv-render${imageStarted ? " is-painting" : ""}`}>
                <span className="fw__pv-renderlabel">
                  {heroReady
                    ? "RENDER COMPLETE"
                    : imageDone
                      ? "ALMOST HERE…"
                      : imageStarted
                        ? "RENDER INCOMING…"
                        : "THE HERO LANDS HERE"}
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>

      <footer className="fw__conduit">
        <div className="fw__track">
          {conduit.map((stage) => (
            <div className={`fw__seg is-${stage.state}`} key={stage.label}>
              <div className="fw__seg-bar">
                <span className="fw__seg-fill" style={{ width: `${stage.pct}%` }} />
                {stage.state === "active" && <span className="fw__seg-flow" />}
              </div>
              <div className="fw__seg-label">
                <span className="fw__seg-dot" />
                {stage.label}
              </div>
            </div>
          ))}
        </div>
        {status && <p className="fw__status">{status}</p>}
      </footer>
    </div>
  );
}

/** The child-facing "what this part adds" line for the source spotlight. */
function contributionOf(s: SourceCreature): string {
  if (s.contribution) return s.contribution;
  if (s.traits?.length) return `Adds ${s.traits.slice(0, 3).join(", ")}.`;
  return s.blurb || "Adds its own wild traits.";
}

/** Playful lab copy built from what each chosen part actually contributes. */
function buildLines(sources: SourceCreature[]): string[] {
  const out: string[] = [];
  sources.forEach((s, i) => {
    const bits = s.traits.length
      ? s.traits
      : s.contribution
        ? [s.contribution.replace(/^Adds\s+/i, "").replace(/\.$/, "")]
        : [];
    bits.slice(0, 3).forEach((bit, j) => {
      out.push(`${VERBS[(i * 3 + j) % VERBS.length]} ${bit.toLowerCase()}...`);
    });
  });
  return out;
}

/** Milestone-driven progress. Every stage STARTS on a real signal; BODY FORGE
    alone is allowed a theatrical crawl (capped at 90) once its start is honest —
    the render itself is one long opaque call with nothing to report. */
function conduitStages(
  creature: CreatureDetail | null,
  heroReady: boolean,
  imageStarted: boolean,
  forgePct: number,
): { label: string; state: StageState; pct: number }[] {
  const recordDone = creature?.record_status === "complete";
  const imageDone = creature?.image_status === "complete";

  let weave = 8;
  if (creature?.name) weave = 34;
  if (typeof creature?.core_stats?.power === "number") weave = 58;
  const abilities = creature?.ability_names?.length ?? 0;
  if (abilities) weave = Math.min(92, 58 + abilities * 8);
  if (recordDone) weave = 100;

  return [
    {
      label: "GENETIC WEAVE",
      state: recordDone ? "done" : "active",
      pct: weave,
    },
    {
      // The render task fires mid-stream (on visual_spec), so BODY FORGE can
      // honestly run while the weave is still filling.
      label: "BODY FORGE",
      state: imageDone ? "done" : imageStarted ? "active" : "waiting",
      pct: imageDone ? 100 : imageStarted ? Math.max(4, forgePct) : 0,
    },
    {
      label: "FINAL RENDER",
      state: heroReady ? "done" : imageDone ? "active" : "waiting",
      pct: heroReady ? 100 : 0,
    },
  ];
}
