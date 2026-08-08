/* Screen 2 — Fusion Lab / ingredient selection (spec §17, §6 guided mode).
   Browsing is visual: four slots, a scroller of big cards, and Randomize. */
import { useEffect, useMemo, useState } from "react";
import type { Go } from "./App";
import { api, ApiError, type SourceCreature } from "./api";
import { Asset, Btn, Empty, Loading, Panel, Stage } from "./ui";

/* PLACEHOLDER — delete once data/source_creatures.json is authored. The real
   library comes from GET /api/library; this only exists so the create -> reveal
   loop is playable while that file is still being written. The banner above the
   picker tells the player (and us) that these are stand-ins. */
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
const CATEGORIES = ["all", "mythic", "extinct", "living"];

export function FusionLab({ go }: { go: Go }) {
  const [sources, setSources] = useState<SourceCreature[] | null>(null);
  const [usingPlaceholders, setUsingPlaceholders] = useState(false);
  const [picks, setPicks] = useState<(SourceCreature | null)[]>([null, null, null, null]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<string | null>(null);

  useEffect(() => {
    api
      .getLibrary()
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
  const activeCategory = category ?? SLOT_HINTS[activeSlot];
  const visible = useMemo(
    () =>
      (sources ?? []).filter(
        (s) => activeCategory === "all" || s.category === activeCategory,
      ),
    [sources, activeCategory],
  );

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
      if (slot === -1) return next;
      next[slot] = source;
      return next;
    });
  }

  function clearSlot(index: number) {
    setPicks((prev) => prev.map((p, i) => (i === index ? null : p)));
  }

  function randomize() {
    if (!sources) return;
    const pool = [...sources];
    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    setPicks([pool[0] ?? null, pool[1] ?? null, pool[2] ?? null, pool[3] ?? null]);
    setError(null);
  }

  async function create() {
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api.createCreature(chosen.map((c) => c.slug));
      go({ name: "reveal", id: out.creature_id });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The fusion chamber is offline.");
      setBusy(false);
    }
  }

  if (!sources) return <Loading label="OPENING THE GENE LIBRARY" />;

  return (
    <div className="lab">
      <header className="lab__head">
        <h1 className="display">
          BUILD YOUR CHIMERA <span className="muted">— STEP {Math.min(chosen.length + 1, 4)} OF 4</span>
        </h1>
        <div className="steps">
          <span className="steps__label num">{chosen.length} OF 4 PARTS CHOSEN</span>
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
          has not landed yet.
        </div>
      )}

      <div className="lab__main">
        <Panel title="YOUR CHIMERA PARTS" accent="purple" className="lab__slots">
          {picks.map((pick, i) => (
            <button
              key={i}
              type="button"
              className={`slot${pick ? " is-filled" : ""}${i === activeSlot && !pick ? " is-active" : ""}`}
              onClick={() => pick && clearSlot(i)}
            >
              <span className="slot__index num">{i + 1}</span>
              {pick ? (
                <>
                  <Asset slot={`sources/${pick.slug}`} label={pick.name} className="slot__art" />
                  <span className="slot__name">{pick.name.toUpperCase()}</span>
                  <span className="slot__state">SELECTED</span>
                </>
              ) : (
                <>
                  <span className="slot__q">?</span>
                  <span className="slot__name">CHOOSE PART</span>
                  <span className="slot__state muted">{SLOT_HINTS[i].toUpperCase()}</span>
                </>
              )}
            </button>
          ))}
        </Panel>

        <div className="lab__stage">
          <Stage caption={chosen.length ? "FUSION PREVIEW" : "AWAITING PARTS"} fusing={ready} />
        </div>

        <Panel title="WHAT EACH PART ADDS" accent="cyan" className="lab__adds">
          {picks.map((pick, i) => (
            <div className="adds" key={i}>
              {pick ? (
                <>
                  <Asset slot={`sources/${pick.slug}`} label={pick.name} className="adds__art" />
                  <div>
                    <div className="adds__name">{pick.name.toUpperCase()}</div>
                    <div className="adds__blurb">{pick.contribution || "Adds its own wild traits."}</div>
                  </div>
                </>
              ) : (
                <>
                  <div className="adds__art adds__art--empty">?</div>
                  <div>
                    <div className="adds__name muted">CHOOSE A PART</div>
                    <div className="adds__blurb">Pick a creature to add its awesome powers!</div>
                  </div>
                </>
              )}
            </div>
          ))}
        </Panel>
      </div>

      <Panel
        title={ready ? "ALL FOUR PARTS CHOSEN" : `CHOOSE PART ${activeSlot + 1}`}
        accent="teal"
        className="lab__picker"
        action={
          <div className="cats">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                type="button"
                className={`cat${activeCategory === c ? " is-active" : ""}`}
                onClick={() => setCategory(c)}
              >
                {c.toUpperCase()}
              </button>
            ))}
          </div>
        }
      >
        {visible.length ? (
          <div className="picker">
            {visible.map((s) => (
              <button
                key={s.slug}
                type="button"
                className={`pcard${takenSlugs.has(s.slug) ? " is-taken" : ""}`}
                onClick={() => place(s)}
                disabled={ready && !takenSlugs.has(s.slug)}
              >
                <Asset slot={`sources/${s.slug}`} label={s.name} className="pcard__art" />
                <span className="pcard__name">{s.name.toUpperCase()}</span>
                <span className="pcard__cat">{s.category.toUpperCase()}</span>
              </button>
            ))}
          </div>
        ) : (
          <Empty title="The gene library is empty" hint="Authored source creatures have not landed yet." />
        )}
      </Panel>

      {error && <div className="error">{error}</div>}

      <footer className="lab__foot">
        <Btn accent="ghost" onClick={() => go({ name: "home" })}>
          BACK TO HOME
        </Btn>
        <Btn accent="purple" onClick={randomize} disabled={busy}>
          RANDOMIZE
        </Btn>
        <Btn
          accent="cyan"
          size="lg"
          onClick={create}
          disabled={!ready || busy}
          sub={ready ? "FUSE AND REVEAL" : "PICK FOUR PARTS FIRST"}
        >
          {busy ? "FUSING…" : "CREATE CHIMERA"}
        </Btn>
      </footer>
    </div>
  );
}
