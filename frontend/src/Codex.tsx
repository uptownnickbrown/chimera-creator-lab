/* Screen 4 — Codex (spec §14, art-direction/codex.png). Sorting reads as
   questions, never as a spreadsheet config: a filter rail on the left, the
   archive grid in the middle, and the selected chimera standing on its own
   platform on the right. */
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Go } from "./App";
import {
  api,
  getLibraryCached,
  type CodexSort,
  type CreatureDetail,
  type CreatureSummary,
  type SourceCreature,
} from "./api";
import {
  Asset,
  Badge,
  Btn,
  CreatureCard,
  Empty,
  FitText,
  Loading,
  MoveChips,
  Panel,
  PartImg,
  RarityBadge,
  Stage,
  StatRow,
  TraitChips,
} from "./ui";

const SORTS: { key: CodexSort; label: string }[] = [
  { key: "newest", label: "ALL" },
  { key: "favorites", label: "FAVORITES" },
  { key: "winners", label: "WINNERS" },
  { key: "biggest", label: "BIGGEST" },
  { key: "fastest", label: "FASTEST" },
  { key: "strongest", label: "STRONGEST" },
];

export function Codex({ go, selectedId }: { go: Go; selectedId?: number }) {
  const [sort, setSort] = useState<CodexSort>("newest");
  const [rows, setRows] = useState<CreatureSummary[] | null>(null);
  const [selected, setSelected] = useState<CreatureDetail | null>(null);
  const [query, setQuery] = useState("");
  const [libSources, setLibSources] = useState<SourceCreature[]>([]);
  /** RELEASE (delete) failsafe: two-tap confirm, quiet. */
  const [confirmRelease, setConfirmRelease] = useState(false);
  const [releaseError, setReleaseError] = useState<string | null>(null);

  useEffect(() => {
    getLibraryCached()
      .then((lib) => setLibSources(lib.sources))
      .catch(() => undefined);
  }, []);

  /* The four donor parts — library entries where they exist (painted portraits
     or a summoned part's /media portrait), bare slugs otherwise. */
  const libBySlug = useMemo(
    () => new Map(libSources.map((s) => [s.slug, s])),
    [libSources],
  );

  const load = useCallback(async (which: CodexSort) => {
    setRows(await api.listCreatures(which).catch(() => []));
  }, []);

  useEffect(() => {
    load(sort);
  }, [load, sort]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows ?? [];
    return (rows ?? []).filter((c) =>
      `${c.name} ${c.title} ${c.rarity} ${c.role} ${c.sources.join(" ")}`.toLowerCase().includes(q),
    );
  }, [rows, query]);

  useEffect(() => {
    /* Default to a chimera that actually has a render — landing on a failed
       splice would show the child an empty pedestal for no reason. */
    const first = rows?.find((c) => c.hero_image_path || c.thumb_path) ?? rows?.[0];
    const id = selectedId ?? first?.id;
    if (!id) {
      setSelected(null);
      return;
    }
    let cancelled = false;
    api
      .getCreature(id)
      .then((c) => !cancelled && setSelected(c))
      .catch(() => !cancelled && setSelected(null));
    return () => {
      cancelled = true;
    };
  }, [selectedId, rows]);

  /* A new selection always resets the release confirm — no armed buttons. */
  useEffect(() => {
    setConfirmRelease(false);
    setReleaseError(null);
  }, [selected?.id]);

  async function toggleFavorite() {
    if (!selected) return;
    await api.toggleFavorite(selected.id);
    setSelected(await api.getCreature(selected.id));
    load(sort);
  }

  async function release() {
    if (!selected) return;
    try {
      await api.deleteCreature(selected.id);
      setSelected(null);
      setConfirmRelease(false);
      go({ name: "codex" });
      load(sort);
    } catch {
      setReleaseError("The wild is not accepting releases right now. Try again soon.");
    }
  }

  async function reroll() {
    if (!selected) return;
    await api.rerollName(selected.id);
    setSelected(await api.getCreature(selected.id));
    load(sort);
  }

  if (!rows) return <Loading label="OPENING THE CODEX" />;

  const favourites = rows.filter((c) => c.favorite).length;
  const painted = rows.filter((c) => c.hero_image_path || c.thumb_path).length;

  return (
    <div className="codex screen-in">
      <aside className="codex__rail">
        <header className="codex__title">
          <h1 className="display display--xl">MY CODEX</h1>
          <p className="codex__sub">CREATURE ARCHIVE</p>
          <p className="lede">Every chimera you have ever built, kept forever.</p>
        </header>

        <div className="codex__filters">
          {SORTS.map((s) => (
            <button
              key={s.key}
              type="button"
              className={`filter${sort === s.key ? " is-active" : ""}`}
              onClick={() => setSort(s.key)}
            >
              <Asset
                slot={`icons/sort_${s.key}`}
                label=""
                className="filter__icon"
                tint={s.key === "favorites" || s.key === "winners" ? "gold" : undefined}
              />
              {s.label}
            </button>
          ))}
        </div>

        <Panel title="CODEX PROGRESS" accent="purple" className="codex__progress">
          <div className="progress">
            <div className="progress__row">
              <Asset slot="icons/tile_codex" label="" className="progress__icon" tint="purple" />
              <div>
                <div className="progress__value num">{rows.length}</div>
                <div className="progress__label">CHIMERAS DISCOVERED</div>
              </div>
            </div>
            <div className="progress__bar">
              <span style={{ width: `${rows.length ? (painted / rows.length) * 100 : 0}%` }} />
            </div>
            <div className="progress__foot num">
              {painted} PAINTED · {favourites} FAVOURITE{favourites === 1 ? "" : "S"}
            </div>
          </div>
        </Panel>
      </aside>

      <Panel
        accent="cyan"
        className="codex__grid"
        title={`${SORTS.find((s) => s.key === sort)?.label ?? "ALL"} — ${visible.length}`}
        action={
          <label className="search">
            <Asset slot="icons/search" label="" className="search__icon" />
            <input
              type="search"
              value={query}
              placeholder="Search chimeras…"
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search your chimeras"
            />
          </label>
        }
      >
        {visible.length ? (
          <div className="codex__scroll">
            <div className="grid">
              {visible.map((c) => (
                <CreatureCard
                  key={c.id}
                  creature={c}
                  selected={c.id === selected?.id}
                  onClick={() => go({ name: "codex", id: c.id })}
                  corner={c.championships > 0 ? <Badge tone="gold">CHAMP</Badge> : undefined}
                />
              ))}
            </div>
          </div>
        ) : (
          <Empty
            title={query ? `Nothing matches “${query}”` : sort === "favorites" ? "No favourites yet" : "No chimeras yet"}
            hint={query ? "Try another name." : "Build one in the Fusion Lab and it lands here forever."}
          />
        )}
      </Panel>

      <aside className="codex__detail">
        {selected ? (
          <Panel accent="cyan" className="detail">
            <header className="detail__head">
              <div className="detail__id">
                <h2 className="detail__name">
                  <FitText>{(selected.name || "UNNAMED SPLICE").toUpperCase()}</FitText>
                </h2>
                <div className="detail__badges">
                  <RarityBadge rarity={selected.rarity} />
                  <span className="muted">{selected.title || selected.role}</span>
                </div>
              </div>
              <button
                type="button"
                className={`starbtn${selected.favorite ? " is-on" : ""}`}
                onClick={toggleFavorite}
                aria-label={selected.favorite ? "Remove favourite" : "Make favourite"}
                title={selected.favorite ? "Remove favourite" : "Make favourite"}
              >
                <Asset slot="icons/star" label="" tint="gold" />
              </button>
            </header>

            {/* No pedestal in the codex detail: plain render, grounded on a
                soft shadow (pedestal policy, UI_STANDARD). */}
            <div className="detail__stage">
              <Stage plain creature={selected} gold={selected.championships > 0} caption="RENDER PENDING" />
            </div>

            <div className="detail__record">
              {[
                ["WINS", String(selected.wins)],
                ["LOSSES", String(selected.losses)],
                ["WIN RATE", `${selected.win_rate}%`],
                ["TITLES", String(selected.championships)],
              ].map(([k, v]) => (
                <div key={k}>
                  <span className="detail__v num">{v}</span>
                  <span className="detail__k">{k}</span>
                </div>
              ))}
            </div>

            <StatRow compact stats={selected.core_stats} />

            {selected.sources.length > 0 && (
              <section className="detail__section">
                <h3 className="detail__subhead">FUSED FROM</h3>
                <div className="detail__parts">
                  {selected.sources.map((slug) => {
                    const p = libBySlug.get(slug);
                    const name =
                      p?.name ?? slug.replace(/^custom\//, "").replace(/[_-]/g, " ");
                    return (
                      <div className="detail__part" key={slug} title={p?.contribution || name}>
                        <span className="detail__part-img">
                          <PartImg source={p} slug={slug} label={name} />
                        </span>
                        <span className="detail__part-name">
                          <FitText>{name.toUpperCase()}</FitText>
                        </span>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {selected.abilities.length > 0 && (
              <section className="detail__section">
                <h3 className="detail__subhead">MOVES</h3>
                <MoveChips abilities={selected.abilities} />
              </section>
            )}

            {(selected.strengths.length > 0 ||
              selected.weaknesses.length > 0 ||
              selected.fun_fact) && (
              <section className="detail__section">
                <TraitChips
                  strengths={selected.strengths}
                  weaknesses={selected.weaknesses}
                  funFact={selected.fun_fact || undefined}
                />
              </section>
            )}

            {Object.keys(selected.records).length > 0 && (
              <div className="detail__records">
                {Object.entries(selected.records).map(([k, v]) => (
                  <span className="plaque" key={k}>
                    <Asset slot={`icons/record_${k}`} label="" className="plaque__icon" tint="gold" />
                    <span className="plaque__text">
                      <b>{k.replace(/_/g, " ").toUpperCase()}</b>
                      {String(v)}
                    </span>
                  </span>
                ))}
              </div>
            )}

            {confirmRelease ? (
              <div className="release">
                <p className="release__ask">
                  Release {selected.name || "this chimera"} into the wild? It leaves your
                  Codex forever.
                </p>
                <div className="release__row">
                  <Btn accent="ghost" size="sm" onClick={() => setConfirmRelease(false)}>
                    KEEP IT
                  </Btn>
                  <button type="button" className="release__go" onClick={release}>
                    YES — RELEASE
                  </button>
                </div>
                {releaseError && <div className="error">{releaseError}</div>}
              </div>
            ) : (
              <div className="detail__actions">
                <Btn accent="ghost" size="sm" onClick={reroll}>
                  REROLL NAME
                </Btn>
                <Btn accent="gold" size="sm" icon="icons/nav_arena" onClick={() => go({ name: "arena" })}>
                  GO TO ARENA
                </Btn>
                <button
                  type="button"
                  className="release__quiet"
                  onClick={() => setConfirmRelease(true)}
                  title={`Release ${selected.name || "this chimera"}`}
                >
                  RELEASE
                </button>
              </div>
            )}
          </Panel>
        ) : (
          <Panel accent="cyan" className="detail">
            <Empty title="Nothing selected" hint="Tap a card to see its full record." />
          </Panel>
        )}
      </aside>
    </div>
  );
}
