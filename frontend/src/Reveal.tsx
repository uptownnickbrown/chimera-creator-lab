/* Screen 3 — Creation Reveal (spec §17, §7 REVEAL).

   One component owns the whole tail of the creation flow: it polls the staged
   backend, plays the Fusion Wait while the record streams and the hero render
   cooks, then detonates the reveal the moment the finished PNG has decoded.
   The creature is the star — panels frame it, they never crowd it. */
import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import type { Go } from "./App";
import { api, getLibraryCached, type CreatureDetail, type SourceCreature } from "./api";
import { FusionWait } from "./FusionWait";
import {
  Asset,
  Badge,
  Btn,
  CreatureImg,
  FitText,
  Panel,
  PartImg,
  RarityBadge,
  StatRow,
} from "./ui";

/* Four abilities all wearing the same glyph reads as a placeholder; the stat
   icons give each one its own painted mark. */
const ABILITY_ICONS = [
  "icons/ability_generic",
  "icons/stat_special",
  "icons/stat_power",
  "icons/stat_speed",
];

/* A few early seed records glued extra list entries into one string with a
   raw '","' separator (a data-side parse slip). The kid never sees that
   artifact: split the entries apart, strip stray quotes, and keep the three
   the reveal composition is built around — clean records already have three,
   so this is a no-op for them. Every kept sentence renders in full. */
function cleanFacts(rows: string[], max = 3): string[] {
  return rows
    .flatMap((r) => r.split(/"\s*,\s*"/))
    .map((r) => r.replace(/^"+|"+$/g, "").trim())
    .filter(Boolean)
    .slice(0, max);
}

const POLL_MS = 1500;
/** White-out length; the reveal mounts underneath it and is lit as it clears. */
const FLASH_MS = 300;

export function Reveal({ go, creatureId }: { go: Go; creatureId: number }) {
  const [creature, setCreature] = useState<CreatureDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [heroReady, setHeroReady] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [flashing, setFlashing] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const timer = useRef<number | null>(null);
  /* Did we ever show the wait? A codex revisit lands already-complete and must
     not fire a white-out at a child who did not ask for one. */
  const waited = useRef(false);
  /* Library lookup so FUSED FROM can render summoned parts (their portraits
     live on /media, not in the painted /assets/parts set). */
  const [libBySlug, setLibBySlug] = useState<Map<string, SourceCreature> | null>(null);
  useEffect(() => {
    getLibraryCached()
      .then((lib) => setLibBySlug(new Map(lib.sources.map((s) => [s.slug, s]))))
      .catch(() => {}); // painted-asset fallback still renders
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const row = await api.getCreature(creatureId);
        if (cancelled) return;
        setCreature(row);
        const settled =
          row.record_status !== "generating" &&
          (row.image_status === "complete" || row.image_status === "failed");
        if (!settled) {
          waited.current = true;
          timer.current = setTimeout(poll, POLL_MS) as unknown as number;
        }
      } catch {
        if (!cancelled) setError("That chimera could not be found.");
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [creatureId, retrying]);

  /* FINAL RENDER is a real stage: decode the hero before anyone sees it, so the
     creature never pops in half-drawn behind the flash. */
  const hero = creature?.image_status === "complete" ? creature.hero_image_path : null;
  useEffect(() => {
    if (!hero) return;
    let dead = false;
    const img = new Image();
    img.onload = () => !dead && setHeroReady(true);
    img.onerror = () => !dead && setHeroReady(true); // <MediaImg> owns the fallback
    img.src = hero;
    return () => {
      dead = true;
    };
  }, [hero]);

  useEffect(() => {
    if (!heroReady || revealed) return;
    if (!waited.current) {
      setRevealed(true); // straight from the Codex: no chamber, no flash
      return;
    }
    setFlashing(true);
    const a = setTimeout(() => setRevealed(true), 140);
    const b = setTimeout(() => setFlashing(false), FLASH_MS + 420);
    return () => {
      clearTimeout(a);
      clearTimeout(b);
    };
  }, [heroReady, revealed]);

  const retryImage = useCallback(async () => {
    if (!creature) return;
    try {
      await api.retryImage(creature.id);
      setRetrying((n) => !n); // restart the poll loop
    } catch {
      setError("The lab could not restart the render. Try again in a moment.");
    }
  }, [creature]);

  if (error) return <div className="error">{error}</div>;

  const recordFailed = creature?.record_status === "failed";
  const imageFailed = creature?.image_status === "failed";

  if (recordFailed) {
    return (
      <div className="rv__recharge">
        <p className="eyebrow">FUSION INTERRUPTED</p>
        <h1 className="display">THE LAB IS RECHARGING</h1>
        <p className="lede">
          That splice did not take. Nothing is lost — pick four parts and fuse again.
        </p>
        <Btn accent="cyan" size="lg" onClick={() => go({ name: "lab" })}>
          BACK TO THE FUSION LAB
        </Btn>
      </div>
    );
  }

  /* Still cooking (or the render failed and there is nothing to reveal yet). */
  if (!revealed && !imageFailed) {
    return (
      <>
        {flashing && <div className="rv__flash" aria-hidden="true" />}
        <FusionWait creature={creature} creatureId={creatureId} heroReady={heroReady} />
      </>
    );
  }

  if (!creature) return null;

  const title = creature.title || creature.role;

  return (
    <>
      {flashing && <div className="rv__flash" aria-hidden="true" />}
      <div className="rv">
        <section className="rv__intro">
          <p className="eyebrow rv-in" style={anim(0)}>
            NEW CHIMERA
          </p>
          <h1 className="display display--xl rv-in" style={anim(60)}>
            CREATED!
          </h1>
          <div className="rule rv-in" style={anim(120)} />
          <p className="lede rv-in" style={anim(160)}>
            Your fusion is complete. A brand new chimera is born!
          </p>

          <h2 className="rv__name rv-in" style={anim(380)}>
            {creature.name.toUpperCase()}
          </h2>
          <div className="rv__badges rv-stamp" style={anim(760)}>
            <RarityBadge rarity={creature.rarity} />
            {imageFailed && <Badge tone="red">ART PENDING</Badge>}
          </div>
          {title && (
            <p className="rv__title rv-in" style={anim(460)}>
              {title}
            </p>
          )}

          {creature.fun_fact && (
            <div className="rv__topfact rv-in" style={anim(1500)}>
              <Asset slot="icons/fact_fun" label="" className="fact__icon" />
              <div>
                <div className="fact__title">TOP FACT</div>
                <div className="fact__blurb">{creature.fun_fact}</div>
              </div>
            </div>
          )}
        </section>

        <section className="rv__stage">
          <div className="rv__platform">
            <Asset slot="lab/platform" label="" />
          </div>
          <div className={`rv__hero${imageFailed ? " is-empty" : ""}`} style={anim(120)}>
            {imageFailed ? (
              <div className="rv__recharge rv__recharge--inline">
                <p className="eyebrow">RENDER PAUSED</p>
                <h2 className="display">THE PAINT POTS RAN DRY</h2>
                <p className="lede">
                  {creature.name || "Your chimera"} is safely saved. The lab can try the
                  picture again.
                </p>
                <Btn accent="cyan" size="lg" onClick={retryImage}>
                  TRY THE RENDER AGAIN
                </Btn>
              </div>
            ) : (
              <CreatureImg creature={creature} prefer="hero" />
            )}
          </div>
        </section>

        <aside className="rv__side">
          <div className="rv__side-scroll">
          <Panel title="TOP FACTS" accent="cyan">
            {cleanFacts(creature.strengths).map((s, i) => (
              <div className="fact rv-cascade" key={`s${i}`} style={anim(1150 + i * 110)}>
                <Asset slot="icons/fact_strength" label="" className="fact__icon" />
                <div>
                  <div className="fact__title">STRENGTH</div>
                  <div className="fact__blurb">{s}</div>
                </div>
              </div>
            ))}
          </Panel>

          <Panel title="AWESOME ABILITIES" accent="purple">
            {creature.abilities.map((a, i) => (
              <div className="ability rv-cascade" key={a.name} style={anim(1250 + i * 130)}>
                <Asset slot={ABILITY_ICONS[i % ABILITY_ICONS.length]} label="" className="ability__icon" tint="purple" />
                <div>
                  <div className="ability__name">{a.name.toUpperCase()}</div>
                  <div className="ability__blurb">{a.blurb}</div>
                </div>
              </div>
            ))}
          </Panel>
          </div>
        </aside>

        <Panel title="FUSED FROM" accent="cyan" className="rv__fused rv-slide">
          <div className="fused">
            {creature.sources.map((slug, i) => (
              <div className="fused__item" key={slug}>
                {i > 0 && <span className="fused__plus">+</span>}
                <PartImg source={libBySlug?.get(slug)} slug={slug} className="fused__art" />
                <FitText className="fused__name">
                  {(libBySlug?.get(slug)?.name ?? slug.replace(/^custom\//, "").replace(/[_-]/g, " ")).toUpperCase()}
                </FitText>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="CHIMERA STATS" accent="teal" className="rv__stats rv-slide">
          <StatRow stats={creature.core_stats} />
          {creature.weaknesses.length > 0 && (
            <div className="rv__watch">
              <span className="rv__watch-key">WATCH OUT FOR</span>
              <span className="rv__watch-text">{cleanFacts(creature.weaknesses).join(" · ")}</span>
            </div>
          )}
        </Panel>

        <footer className="rv__foot rv-in" style={anim(1700)}>
          <Btn accent="purple" size="lg" icon="icons/tile_codex" onClick={() => go({ name: "codex", id: creature.id })}>
            ADD TO CODEX
          </Btn>
          <Btn accent="cyan" size="lg" icon="icons/nav_fusion" onClick={() => go({ name: "lab" })}>
            MAKE ANOTHER
          </Btn>
          <Btn accent="gold" size="lg" icon="icons/nav_arena" onClick={() => go({ name: "arena" })}>
            ENTER BRACKET
          </Btn>
        </footer>
      </div>
    </>
  );
}

function anim(delayMs: number): CSSProperties {
  return { animationDelay: `${delayMs}ms` };
}
