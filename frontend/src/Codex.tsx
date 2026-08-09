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
  Panel,
  RarityBadge,
  Stage,
  StatRow,
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

  useEffect(() => {
    getLibraryCached()
      .then((lib) => setLibSources(lib.sources))
      .catch(() => undefined);
  }, []);

  /* The four donor parts, resolved to library entries for their portraits. */
  const parts = useMemo(() => {
    if (!selected) return [];
    const bySlug = new Map(libSources.map((s) => [s.slug, s]));
    return (selected.sources ?? [])
      .map((slug) => bySlug.get(slug))
      .filter((s): s is SourceCreature => Boolean(s));
  }, [selected, libSources]);

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

  async function toggleFavorite() {
    if (!selected) return;
    await api.toggleFavorite(selected.id);
    setSelected(await api.getCreature(selected.id));
    load(sort);
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
          <Panel title="SELECTED CHIMERA" accent="cyan" className="detail">
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

            <div className="detail__stage">
              <Stage creature={selected} gold={selected.championships > 0} caption="RENDER PENDING" />
            </div>

            <div className="detail__record">
              {[
                ["WINS", String(selected.wins)],
                ["LOSSES", String(selected.losses)],
                ["WIN RATE", `${selected.win_rate}%`],
                ["TITLES", String(selected.championships)],
              ].map(([k, v]) => (
                <div key={k}>
                  <div className="detail__k">{k}</div>
                  <div className="detail__v num">{v}</div>
                </div>
              ))}
            </div>

            <StatRow stats={selected.core_stats} />

            {parts.length > 0 && (
              <section className="detail__section">
                <h3 className="detail__subhead">FUSED FROM</h3>
                <div className="detail__parts">
                  {parts.map((p) => (
                    <div className="detail__part" key={p.slug} title={p.contribution || p.name}>
                      <span className="detail__part-img">
                        <Asset slot={`parts/${p.slug}`} label={p.name} />
                      </span>
                      <span className="detail__part-name">
                        <FitText>{p.name.toUpperCase()}</FitText>
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {selected.abilities.length > 0 && (
              <section className="detail__section">
                <h3 className="detail__subhead">MOVES</h3>
                <div className="detail__moves">
                  {selected.abilities.map((a) => (
                    <article className="detail__move" key={a.name}>
                      <h4 className="detail__move-name">
                        <FitText>{String(a.name ?? "").toUpperCase()}</FitText>
                      </h4>
                      <p className="detail__move-blurb">{a.blurb}</p>
                    </article>
                  ))}
                </div>
              </section>
            )}

            {selected.fun_fact && (
              <p className="detail__fact">
                <b>FUN FACT</b> {selected.fun_fact}
              </p>
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

            <div className="detail__actions">
              <Btn accent="ghost" size="sm" onClick={reroll}>
                REROLL NAME
              </Btn>
              <Btn accent="gold" size="sm" icon="icons/nav_arena" onClick={() => go({ name: "arena" })}>
                GO TO ARENA
              </Btn>
            </div>
          </Panel>
        ) : (
          <Panel title="SELECTED CHIMERA" accent="cyan" className="detail">
            <Empty title="Nothing selected" hint="Tap a card to see its full record." />
          </Panel>
        )}
      </aside>
    </div>
  );
}
