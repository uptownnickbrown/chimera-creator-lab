/* Hall of Champions (spec §16) — the reason old creatures still matter. */
import { useEffect, useState } from "react";
import type { Go } from "./App";
import { api, type HallView } from "./api";
import { Asset, Badge, Btn, CreatureCard, CreatureImg, Empty, Loading, Panel } from "./ui";

export function Hall({ go }: { go: Go }) {
  const [hall, setHall] = useState<HallView | null>(null);

  useEffect(() => {
    api
      .getHall()
      .then(setHall)
      .catch(() => setHall({ champions: [], top_winners: [], records: [] }));
  }, []);

  if (!hall) return <Loading label="OPENING THE HALL" />;

  return (
    <div className="hall">
      <header className="hall__head">
        <h1 className="display display--xl">HALL OF CHAMPIONS</h1>
        <p className="lede">Every champion, every record, kept forever.</p>
      </header>

      <div className="hall__body">
        <Panel title="CHAMPIONS" accent="gold" className="hall__champs">
          {hall.champions.length ? (
            <div className="grid">
              {hall.champions.map((c) => (
                <CreatureCard
                  key={c.id}
                  creature={c}
                  onClick={() => go({ name: "codex", id: c.id })}
                  corner={<Badge tone="gold">{c.championships}x</Badge>}
                />
              ))}
            </div>
          ) : (
            <Empty title="No champions yet" hint="Run a bracket in the Arena to crown one." />
          )}
        </Panel>

        <Panel title="TOP WINNERS" accent="cyan" className="hall__winners">
          {hall.top_winners.length ? (
            <ol className="rank">
              {hall.top_winners.map((c, i) => (
                <li key={c.id}>
                  <button type="button" onClick={() => go({ name: "codex", id: c.id })}>
                    <span className="rank__n num">{i + 1}</span>
                    <CreatureImg creature={c} className="rank__art" />
                    <span className="rank__name">{c.name.toUpperCase()}</span>
                    <span className="rank__wins num">{c.wins}W</span>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <Empty title="No battles fought yet" />
          )}
        </Panel>

        <Panel title="RECORDS" accent="purple" className="hall__records">
          {hall.records.length ? (
            <div className="records">
              {hall.records.map((r) => (
                <div className="record" key={r.key}>
                  <Asset slot={`icons/record_${r.key}`} label="" className="record__icon" />
                  <div>
                    <div className="record__label">{r.label.toUpperCase()}</div>
                    <div className="record__holder">{r.creature?.name ?? "—"}</div>
                  </div>
                  <div className="record__value num">{r.value}</div>
                </div>
              ))}
            </div>
          ) : (
            <Empty title="No records yet" hint="Build a chimera and the records start filling in." />
          )}
        </Panel>
      </div>

      <footer className="hall__foot">
        <Btn accent="ghost" onClick={() => go({ name: "codex" })}>
          BACK TO CODEX
        </Btn>
        <Btn accent="gold" size="lg" onClick={() => go({ name: "arena" })}>
          RUN A TOURNAMENT
        </Btn>
      </footer>
    </div>
  );
}
