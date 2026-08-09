/* Screen 2 — Fusion Lab / ingredient selection (spec §17, §6 guided mode,
   art-direction/build.png).

   Four slot cards on the left, the proto-fusion cluster hovering over the lab
   platform in the middle, what-each-part-adds on the right, and one big
   portrait rail underneath. Browsing is visual first: the search box is there
   for the child who already knows the animal's name (and its misspellings). */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Go } from "./App";
import { api, ApiError, getLibraryCached, refreshLibrary, type SourceCreature } from "./api";
import { Asset, Btn, Empty, FitText, Loading, Panel, PartImg } from "./ui";
import { stashPicks } from "./FusionWait";
import { SummonModal, SummonRailCard } from "./Summon";

/* PLACEHOLDER — only reached if GET /api/library is empty or unreachable, so
   the create -> reveal loop stays playable. The banner says so out loud. */
const PLACEHOLDER_SOURCES: SourceCreature[] = [
  ["dragon", "Dragon", "mythic", "Adds horns, claws, and fiery breath."],
  ["stegosaurus", "Stegosaurus", "extinct", "Adds big armor plates and extra defense."],
  ["electric-eel", "Electric Eel", "living", "Adds shocking electric attacks."],
  ["great-white-shark", "Great White Shark", "living", "Adds a powerful bite and fast swimming."],
  ["kraken", "Kraken", "mythic", "Adds enormous grabbing tentacles."],
  ["woolly-mammoth", "Woolly Mammoth", "extinct", "Adds huge tusks and thick fur."],
  ["chameleon", "Chameleon", "living", "Adds colour-shifting camouflage."],
  ["peregrine-falcon", "Peregrine Falcon", "living", "Adds the fastest dive in the sky."],
  ["griffin", "Griffin", "mythic", "Adds eagle wings and lion strength."],
  ["triceratops", "Triceratops", "extinct", "Adds a bony frill and three horns."],
  ["cobra", "Cobra", "living", "Adds fast strikes and potent venom."],
  ["octopus", "Octopus", "living", "Adds eight clever, gripping arms."],
].map(([slug, name, category, contribution]) => ({
  slug,
  name,
  category,
  contribution,
  blurb: "",
  traits: [],
  tags: [],
  art: null,
}));

/* Guided mode (spec §6B): the picker nudges mythic / extinct / living / living
   but any four are legal — the category tabs are a suggestion, not a gate. */
const SLOT_HINTS = ["mythic", "extinct", "living", "living"];
const CATEGORIES: { key: string; label: string; icon: string }[] = [
  { key: "all", label: "ALL", icon: "icons/tile_codex" },
  { key: "mythic", label: "MYTHIC", icon: "icons/cat_mythic" },
  { key: "extinct", label: "EXTINCT", icon: "icons/cat_extinct" },
  { key: "living", label: "LIVING", icon: "icons/cat_living" },
];

/** Everything a child might type: the name, the slug, the authored misspellings
    (`aliases`), the tags, and what the part contributes. */
function haystack(s: SourceCreature): string {
  // Name, slug, authored misspellings and tags only: matching the contributes
  // text too would return a tiger for "tiger stripes" on three other animals.
  return [s.name, s.slug.replace(/[-_]/g, " "), ...(s.aliases ?? []), ...(s.tags ?? [])]
    .join(" ")
    .toLowerCase();
}

/** The child-facing "what it adds" line. `contribution` is built from the
    authored `contributes` list; the list itself is the fallback. */
function contributesOf(s: SourceCreature): string {
  if (s.contribution) return s.contribution;
  if (s.traits?.length) return `Adds ${s.traits.slice(0, 3).join(", ")}.`;
  return "Adds its own wild traits.";
}

export function FusionLab({ go }: { go: Go }) {
  const [sources, setSources] = useState<SourceCreature[] | null>(null);
  const [usingPlaceholders, setUsingPlaceholders] = useState(false);
  const [picks, setPicks] = useState<(SourceCreature | null)[]>([null, null, null, null]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  /** Summon modal: null = closed, string = open with that prefill. */
  const [summonQuery, setSummonQuery] = useState<string | null>(null);
  /** Slug that just flew into a slot — wears a highlight pulse briefly. */
  const [flash, setFlash] = useState<string | null>(null);
  const rail = useRef<HTMLDivElement | null>(null);
  const flashTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    getLibraryCached()
      .then((lib) => {
        if (lib.sources.length) {
          setSources(lib.sources);
        } else {
          setSources(PLACEHOLDER_SOURCES);
          setUsingPlaceholders(true);
        }
      })
      .catch(() => {
        setSources(PLACEHOLDER_SOURCES);
        setUsingPlaceholders(true);
      });
  }, []);

  const chosen = picks.filter(Boolean) as SourceCreature[];
  const nextSlot = picks.findIndex((p) => p === null);
  const activeSlot = nextSlot === -1 ? 3 : nextSlot;
  const ready = chosen.length === 4;

  const takenSlugs = useMemo(() => new Set(chosen.map((c) => c.slug)), [chosen]);
  const searching = query.trim().length > 0;
  const activeCategory = searching ? "all" : category ?? SLOT_HINTS[activeSlot];

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (sources ?? [])
      .filter((s) => {
        if (!q && activeCategory !== "all" && s.category !== activeCategory) return false;
        return !q || haystack(s).includes(q);
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [sources, activeCategory, query]);

  useEffect(() => {
    rail.current?.scrollTo({ left: 0 });
  }, [activeCategory, query]);

  function place(source: SourceCreature) {
    setError(null);
    setPicks((prev) => {
      const already = prev.findIndex((p) => p?.slug === source.slug);
      const next = [...prev];
      if (already >= 0) {
        next[already] = null; // tapping a chosen card takes it back out
        return next;
      }
      const slot = next.findIndex((p) => p === null);
      next[slot === -1 ? 3 : slot] = source; // full board: a tap swaps part 4
      return next;
    });
  }

  function clearSlot(index: number) {
    setPicks((prev) => prev.map((p, i) => (i === index ? null : p)));
  }

  /* -- Summon New Creature -------------------------------------------------- */

  /** A summoned/matched part flies into the active slot with a highlight. */
  const summonPlace = useCallback((source: SourceCreature) => {
    setPicks((prev) => {
      if (prev.some((p) => p?.slug === source.slug)) return prev; // already aboard
      const next = [...prev];
      const slot = next.findIndex((p) => p === null);
      next[slot === -1 ? 3 : slot] = source;
      return next;
    });
    setError(null);
    setFlash(source.slug);
    clearTimeout(flashTimer.current);
    flashTimer.current = window.setTimeout(() => setFlash(null), 1800);
  }, []);

  /** A brand-new conjured part: into the rail (under its category) AND the slot. */
  const summonConjured = useCallback(
    (source: SourceCreature) => {
      setSources((prev) => {
        const rest = (prev ?? []).filter((s) => s.slug !== source.slug);
        return [...rest, source];
      });
      setUsingPlaceholders(false);
      summonPlace(source);
    },
    [summonPlace],
  );

  useEffect(() => () => clearTimeout(flashTimer.current), []);

  /* While any summoned part is missing its portrait, poll the library until
     the render lands (backend paints in ~26s; give up after ~4 min). */
  const awaitingArt = useMemo(
    () => (sources ?? []).some((s) => s.custom && !s.art),
    [sources],
  );
  useEffect(() => {
    if (!awaitingArt) return;
    let polls = 0;
    const tick = window.setInterval(async () => {
      polls += 1;
      if (polls > 48) return clearInterval(tick);
      try {
        const lib = await refreshLibrary();
        if (lib.sources.length) {
          setSources(lib.sources);
          setPicks((prev) =>
            prev.map((p) => (p && lib.sources.find((s) => s.slug === p.slug)) || p),
          );
        }
      } catch {
        /* transient — keep polling */
      }
    }, 5000);
    return () => clearInterval(tick);
  }, [awaitingArt]);

  /** Random, but guided: each slot draws from the category it nudges toward. */
  function randomize() {
    if (!sources) return;
    const used = new Set<string>();
    const next = SLOT_HINTS.map((hint) => {
      const pool = sources.filter((s) => s.category === hint && !used.has(s.slug));
      const fallback = sources.filter((s) => !used.has(s.slug));
      const from = pool.length ? pool : fallback;
      if (!from.length) return null;
      const pick = from[Math.floor(Math.random() * from.length)];
      used.add(pick.slug);
      return pick;
    });
    setPicks(next);
    setError(null);
  }

  async function create() {
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api.createCreature(chosen.map((c) => c.slug));
      // Hand the four portraits straight to the Fusion Wait so they are already
      // on screen when the chamber opens — no second of empty chamber.
      stashPicks(out.creature_id, chosen);
      go({ name: "reveal", id: out.creature_id });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The fusion chamber is offline.");
      setBusy(false);
    }
  }

  function nudge(dir: 1 | -1) {
    rail.current?.scrollBy({ left: dir * 560, behavior: "smooth" });
  }

  if (!sources) return <Loading label="OPENING THE GENE LIBRARY" />;

  return (
    <div className="lab screen-in">
      <header className="lab__head">
        <h1 className="display">
          BUILD YOUR CHIMERA
          <span className="lab__step"> — STEP {Math.min(chosen.length + 1, 4)} OF 4</span>
        </h1>
        <div className="steps">
          <span className="steps__label">{chosen.length} OF 4 PARTS CHOSEN</span>
          <span className="steps__dots">
            {[0, 1, 2, 3].map((i) => (
              <i key={i} className={i < chosen.length ? "is-on" : ""} />
            ))}
          </span>
        </div>
      </header>

      {usingPlaceholders && (
        <div className="notice">
          Placeholder parts — the authored gene library (data/source_creatures.json)
          could not be read.
        </div>
      )}

      <div className="lab__main">
        <Panel title="YOUR CHIMERA PARTS" accent="purple" className="lab__slots">
          <div className="slots">
            {picks.map((pick, i) => (
              <button
                key={i}
                type="button"
                className={`slot${pick ? " is-filled" : ""}${i === activeSlot && !pick ? " is-active" : ""}${pick && flash === pick.slug ? " is-flash" : ""}`}
                onClick={() => pick && clearSlot(i)}
                title={pick ? `Remove ${pick.name}` : `Slot ${i + 1}`}
              >
                <span className="slot__index num">{i + 1}</span>
                {pick ? (
                  <>
                    <span className="slot__art">
                      <PartImg source={pick} />
                    </span>
                    <span className="slot__plate">
                      <FitText className="slot__name">{pick.name.toUpperCase()}</FitText>
                      <span className="slot__state">SELECTED</span>
                    </span>
                  </>
                ) : (
                  <>
                    <span className="slot__art slot__art--empty">
                      <Asset slot="ui/tbd" label="" />
                      <b>?</b>
                    </span>
                    <span className="slot__plate">
                      <span className="slot__name muted">CHOOSE PART</span>
                      <span className="slot__state slot__state--hint">{SLOT_HINTS[i].toUpperCase()}</span>
                    </span>
                  </>
                )}
              </button>
            ))}
          </div>
        </Panel>

        <section className="lab__stage">
          <div className={`stage${ready ? " stage--fusing" : ""}`}>
            <div className="stage__glow" />
            <div className="stage__platform">
              <Asset slot="lab/platform" label="" />
            </div>
            <div className="cluster">
              {[0, 1, 2, 3].map((i) => {
                const pick = picks[i];
                return (
                  <div className={`cluster__node cluster__node--${i}${pick ? " is-filled" : ""}`} key={i}>
                    {pick ? (
                      <>
                        <span className="cluster__art">
                          <PartImg source={pick} />
                        </span>
                        <FitText className="cluster__name">{pick.name.toUpperCase()}</FitText>
                      </>
                    ) : (
                      <span className="cluster__art cluster__art--empty">
                        <Asset slot="ui/tbd" label="" />
                      </span>
                    )}
                  </div>
                );
              })}
              <div className="cluster__core" />
            </div>
          </div>
          <p className="lab__hint">
            {ready
              ? "ALL FOUR PARTS LOCKED — FIRE THE CHAMBER"
              : `PICK ${4 - chosen.length} MORE PART${4 - chosen.length === 1 ? "" : "S"} TO START THE FUSION`}
          </p>
        </section>

        <Panel title="WHAT EACH PART ADDS" accent="cyan" className="lab__adds">
          <div className="cascade adds__list">
            {picks.map((pick, i) => (
              <div className={`adds${pick ? " is-filled" : ""}`} key={i}>
                <span className="adds__art">
                  {pick ? <PartImg source={pick} /> : <Asset slot="ui/tbd" label="" />}
                </span>
                <div className="adds__text">
                  {pick ? (
                    <>
                      <FitText className="adds__name">{pick.name.toUpperCase()}</FitText>
                      <div className="adds__blurb">{contributesOf(pick)}</div>
                    </>
                  ) : (
                    <>
                      <div className="adds__name muted">CHOOSE A PART</div>
                      <div className="adds__blurb">Pick a creature to add its powers!</div>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel
        accent="teal"
        className="lab__picker"
        title={ready ? "SWAP A PART — NEW PICKS LAND IN 4" : `CHOOSE PART ${activeSlot + 1}`}
        action={
          <div className="picker__tools">
            <div className="cats">
              {CATEGORIES.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  className={`cat${activeCategory === c.key && !searching ? " is-active" : ""}`}
                  onClick={() => {
                    setQuery("");
                    setCategory(c.key);
                  }}
                >
                  <Asset slot={c.icon} label="" className="cat__icon" tint="teal" />
                  {c.label}
                </button>
              ))}
            </div>
            <label className="search">
              <Asset slot="icons/search" label="" className="search__icon" />
              <input
                type="search"
                value={query}
                placeholder="Search animals…"
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search the gene library"
              />
            </label>
          </div>
        }
      >
        {visible.length ? (
          <div className="railwrap">
            <button type="button" className="rail__arrow rail__arrow--l" onClick={() => nudge(-1)} aria-label="Scroll left">
              ‹
            </button>
            <div className="rail" ref={rail}>
              <SummonRailCard onOpen={() => setSummonQuery("")} />
              {visible.map((s) => (
                <button
                  key={s.slug}
                  type="button"
                  className={`pcard${takenSlugs.has(s.slug) ? " is-taken" : ""}${flash === s.slug ? " is-flash" : ""}`}
                  onClick={() => place(s)}
                  title={ready && !takenSlugs.has(s.slug) ? `Swap ${s.name} into part 4` : s.name}
                >
                  <span className="pcard__art">
                    <PartImg source={s} />
                    {s.custom && <span className="pcard__summoned">SUMMONED</span>}
                    {takenSlugs.has(s.slug) && <span className="pcard__check">✓</span>}
                  </span>
                  <span className="pcard__plate">
                    <Asset
                      slot={`icons/cat_${s.category}`}
                      label=""
                      className="pcard__cat"
                      tint={s.category === "mythic" ? "purple" : s.category === "extinct" ? "gold" : "teal"}
                    />
                    <FitText className="pcard__name">{s.name.toUpperCase()}</FitText>
                  </span>
                </button>
              ))}
            </div>
            <button type="button" className="rail__arrow rail__arrow--r" onClick={() => nudge(1)} aria-label="Scroll right">
              ›
            </button>
          </div>
        ) : (
          <div className="picker__empty">
            <Empty
              title={searching ? `Nothing matches “${query}”` : "The gene library is empty"}
              hint={
                searching
                  ? "No problem — the summoning circle can call brand-new creatures."
                  : undefined
              }
            />
            {searching && (
              <Btn
                accent="purple"
                size="lg"
                icon="icons/nav_fusion"
                onClick={() => setSummonQuery(query.trim())}
              >
                {`SUMMON “${query.trim().toUpperCase()}”`}
              </Btn>
            )}
          </div>
        )}
      </Panel>

      {error && <div className="error">{error}</div>}

      {summonQuery !== null && (
        <SummonModal
          initialQuery={summonQuery}
          onClose={() => setSummonQuery(null)}
          onMatched={summonPlace}
          onConjured={summonConjured}
        />
      )}

      <footer className="lab__foot">
        <Btn accent="ghost" onClick={() => go({ name: "home" })}>
          BACK TO HOME
        </Btn>
        <Btn accent="purple" size="lg" icon="icons/dice" onClick={randomize} disabled={busy}>
          RANDOMIZE
        </Btn>
        <Btn
          accent="teal"
          size="lg"
          icon="icons/nav_fusion"
          onClick={create}
          disabled={!ready || busy}
          sub={ready ? "FUSE AND REVEAL" : `PICK ${4 - chosen.length} MORE`}
        >
          {busy ? "FUSING…" : "CREATE CHIMERA"}
        </Btn>
      </footer>
    </div>
  );
}
