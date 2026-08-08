/* Screen 4 — Codex (spec §14). Sorting reads as questions, never as a
   spreadsheet config. Selected creature gets the detail panel on the right. */
import { useCallback, useEffect, useState } from "react";
import type { Go } from "./App";
import { api, type CodexSort, type CreatureDetail, type CreatureSummary } from "./api";
import { Asset, Badge, Btn, CreatureCard, Empty, Loading, Panel, RarityBadge, StatRow } from "./ui";

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

  const load = useCallback(async (which: CodexSort) => {
    setRows(await api.listCreatures(which).catch(() => []));
  }, []);

  useEffect(() => {
    load(sort);
  }, [load, sort]);

  useEffect(() => {
    const id = selectedId ?? rows?.[0]?.id;
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

  return (
    <div className="codex">
      <aside className="codex__rail">
        <h1 className="display">MY CODEX</h1>
        <p className="codex__sub">CREATURE ARCHIVE</p>
        <p className="lede">Browse every chimera you have created.</p>
        <div className="codex__filters">
          {SORTS.map((s) => (
            <button
              key={s.key}
              type="button"
              className={`filter${sort === s.key ? " is-active" : ""}`}
              onClick={() => setSort(s.key)}
            >
              <Asset slot={`icons/sort_${s.key}`} label="" className="filter__icon" />
              {s.label}
            </button>
          ))}
        </div>
        <Panel title="CODEX PROGRESS" accent="purple">
          <div className="progress">
            <div className="progress__value num">{rows.length}</div>
            <div className="progress__label">CHIMERAS DISCOVERED</div>
          </div>
        </Panel>
      </aside>

      <section className="codex__grid">
        {rows.length ? (
          <div className="grid">
            {rows.map((c) => (
              <CreatureCard
                key={c.id}
                creature={c}
                selected={c.id === selected?.id}
                onClick={() => go({ name: "codex", id: c.id })}
                corner={c.championships > 0 ? <Badge tone="gold">CHAMP</Badge> : undefined}
              />
            ))}
          </div>
        ) : (
          <Empty
            title={sort === "favorites" ? "No favorites yet" : "No chimeras yet"}
            hint="Build one in the Fusion Lab and it lands here forever."
          />
        )}
      </section>

      <aside className="codex__detail">
        {selected ? (
          <Panel title="SELECTED CHIMERA" accent="cyan">
            <h2 className="detail__name">{selected.name.toUpperCase()}</h2>
            <div className="detail__badges">
              <RarityBadge rarity={selected.rarity} />
              <span className="muted">{selected.role}</span>
            </div>
            <Asset
              slot={`creatures/${selected.id}`}
              label={selected.name}
              className="detail__art"
            />
            <div className="detail__record">
              <div>
                <div className="detail__k">WINS</div>
                <div className="detail__v num">{selected.wins}</div>
              </div>
              <div>
                <div className="detail__k">LOSSES</div>
                <div className="detail__v num">{selected.losses}</div>
              </div>
              <div>
                <div className="detail__k">WIN RATE</div>
                <div className="detail__v num">{selected.win_rate}%</div>
              </div>
              <div>
                <div className="detail__k">TITLES</div>
                <div className="detail__v num">{selected.championships}</div>
              </div>
            </div>
            <StatRow stats={selected.core_stats} />
            {Object.keys(selected.records).length > 0 && (
              <div className="detail__records">
                {Object.entries(selected.records).map(([k, v]) => (
                  <Badge key={k} tone="gold">
                    {String(v)}
                  </Badge>
                ))}
              </div>
            )}
            <div className="detail__actions">
              <Btn accent={selected.favorite ? "gold" : "ghost"} onClick={toggleFavorite}>
                {selected.favorite ? "FAVORITED" : "FAVORITE"}
              </Btn>
              <Btn accent="ghost" onClick={reroll}>
                REROLL NAME
              </Btn>
              <Btn accent="gold" onClick={() => go({ name: "arena" })}>
                GO TO ARENA
              </Btn>
            </div>
          </Panel>
        ) : (
          <Panel title="SELECTED CHIMERA" accent="cyan">
            <Empty title="Nothing selected" hint="Tap a card to see its full record." />
          </Panel>
        )}
      </aside>
    </div>
  );
}
