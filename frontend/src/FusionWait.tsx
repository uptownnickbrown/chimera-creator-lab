/* The Fusion Wait — the 30-75s the chimera takes to cook, staged as theatre
   rather than a spinner (ARCHITECTURE.md: staged reveal; brief: never a bare
   spinner).

   Phase A  IGNITION   the four chosen portraits fly into the chamber and orbit
   Phase B  SPLICING   name slams in, stat bars fill, ability chips glow on
   Phase C  MEANWHILE  the codex carousel plays while the hero render cooks

   Every progress signal is real: the conduit fills off record_status /
   ability_names / core_stats / image_status, never off a timer. Segments with
   no field to report (the hero render is one long opaque call) show flowing
   energy instead of a lying percentage. */
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  api,
  getLibraryCached,
  type CreatureDetail,
  type CreatureSummary,
  type SourceCreature,
} from "./api";
import { Asset, Badge, CreatureImg, Meter, RarityBadge } from "./ui";

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
const CARD_MS = 4000;
const SPARKS = 18;

const STAT_KEYS = ["power", "speed", "armor", "size", "special"] as const;
const STAT_TONES: Record<string, string> = {
  power: "purple",
  speed: "cyan",
  armor: "green",
  size: "gold",
  special: "orange",
};

type StageState = "done" | "active" | "waiting";

/** One carousel slide — either a past creature or a source-creature fact. */
type Slide =
  | { kind: "creature"; creature: CreatureSummary; ability: string }
  | { kind: "fact"; source: SourceCreature };

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
  const [slides, setSlides] = useState<Slide[]>([]);
  const [line, setLine] = useState(0);
  const [card, setCard] = useState(0);
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

  /* Phase C content, fetched once. The codex list carries no ability names
     (they only stream while a record is generating), so the newest few are
     re-read as details to get one headline ability each. */
  useEffect(() => {
    let dead = false;
    api
      .listCreatures("newest")
      .then(async (rows) => {
        const usable = rows.filter(
          (c) => c.id !== creatureId && c.image_status === "complete" && c.name,
        );
        if (dead) return;
        if (!usable.length) return;
        setSlides(usable.slice(0, 6).map((c) => ({ kind: "creature", creature: c, ability: "" })));
        const detailed = await Promise.all(
          usable.slice(0, 6).map((c) =>
            api
              .getCreature(c.id)
              .then((d) => d.abilities[0]?.name ?? d.role ?? "")
              .catch(() => ""),
          ),
        );
        if (dead) return;
        setSlides(
          usable
            .slice(0, 6)
            .map((c, i) => ({ kind: "creature", creature: c, ability: detailed[i] })),
        );
      })
      .catch(() => undefined);
    return () => {
      dead = true;
    };
  }, [creatureId]);

  /* First creature ever: tease the four sources instead of an empty carousel. */
  const deck: Slide[] = useMemo(
    () => (slides.length ? slides : sources.map((s) => ({ kind: "fact", source: s }))),
    [slides, sources],
  );

  const lines = useMemo(() => buildLines(sources), [sources]);

  useEffect(() => {
    if (lines.length < 2) return;
    const t = setInterval(() => setLine((i) => (i + 1) % lines.length), LINE_MS);
    return () => clearInterval(t);
  }, [lines.length]);

  useEffect(() => {
    if (deck.length < 2) return;
    const t = setInterval(() => setCard((i) => (i + 1) % deck.length), CARD_MS);
    return () => clearInterval(t);
  }, [deck.length]);

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

  const conduit = conduitStages(creature, heroReady);

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
              <span className="num muted">{abilityNames.length} / 4</span>
            </header>
            <div className="panel__body">
              <div className="fw__chips">
                {abilityNames.map((name) => (
                  <span className="fw__chip" key={name}>
                    {name.toUpperCase()}
                  </span>
                ))}
                {Array.from({ length: Math.max(0, 4 - abilityNames.length) }).map((_, i) => (
                  <span className="fw__chip fw__chip--ghost" key={`ghost${i}`} />
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
                      <Asset slot={`parts/${s.slug}`} label={s.name} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
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
        </section>

        <section className="fw__rail">
          <div className={`panel panel--cyan fw__panel fw__meanwhile${deck.length ? " is-on" : ""}`}>
            <header className="panel__head">
              <h2>{slides.length ? "MEANWHILE IN YOUR LAB" : "WHILE YOU WAIT"}</h2>
            </header>
            <div className="panel__body">
              <div className="fw__deck">
                {deck.map((slide, i) => (
                  <article
                    className={`fw__slide${i === card % deck.length ? " is-on" : ""}`}
                    key={slide.kind === "creature" ? `c${slide.creature.id}` : `s${slide.source.slug}`}
                  >
                    {slide.kind === "creature" ? (
                      <>
                        <div className="fw__slide-art">
                          <CreatureImg creature={slide.creature} />
                        </div>
                        <h3 className="fw__slide-name">{slide.creature.name.toUpperCase()}</h3>
                        <div className="fw__slide-meta">
                          <RarityBadge rarity={slide.creature.rarity} />
                          <span className="num">
                            {slide.creature.wins}W - {slide.creature.losses}L
                          </span>
                        </div>
                        {slide.ability && (
                          <p className="fw__slide-line">
                            <span className="fw__slide-key">SIGNATURE</span>
                            {slide.ability}
                          </p>
                        )}
                      </>
                    ) : (
                      <>
                        <div className="fw__slide-art">
                          <Asset slot={`parts/${slide.source.slug}`} label={slide.source.name} />
                        </div>
                        <h3 className="fw__slide-name">{slide.source.name.toUpperCase()}</h3>
                        <p className="fw__slide-line">
                          <span className="fw__slide-key">DID YOU KNOW</span>
                          {slide.source.blurb || slide.source.contribution}
                        </p>
                      </>
                    )}
                  </article>
                ))}
                {!deck.length && (
                  <article className="fw__slide is-on">
                    <h3 className="fw__slide-name">YOUR FIRST CHIMERA</h3>
                    <p className="fw__slide-line">
                      Every creature you build lands in the Codex, ready to battle.
                    </p>
                  </article>
                )}
              </div>
              {deck.length > 1 && (
                <div className="fw__dots fw__dots--deck">
                  {deck.map((_, i) => (
                    <i key={i} className={i === card % deck.length ? "is-on" : ""} />
                  ))}
                </div>
              )}
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
        <p className="fw__status">
          {imageDone
            ? "RENDER COMPLETE"
            : recordDone
              ? "PAINTING THE HERO RENDER — THIS IS THE SLOW, GOOD BIT"
              : "READING THE FUSED GENOME"}
        </p>
      </footer>
    </div>
  );
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

/** Milestone-driven progress. Nothing here is a timer. */
function conduitStages(
  creature: CreatureDetail | null,
  heroReady: boolean,
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
      label: "BODY FORGE",
      state: imageDone ? "done" : recordDone ? "active" : "waiting",
      pct: imageDone ? 100 : 0,
    },
    {
      label: "FINAL RENDER",
      state: heroReady ? "done" : imageDone ? "active" : "waiting",
      pct: heroReady ? 100 : 0,
    },
  ];
}
