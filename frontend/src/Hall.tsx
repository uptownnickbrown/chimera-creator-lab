/* Hall of Champions (spec §16) — the reason old creatures still matter.
   Gold everywhere: the reigning champion stands on the gold platform above the
   pedestal, records hang as plaques, and the winners' ladder runs beside it. */
import { useEffect, useState } from "react";
import type { Go } from "./App";
import { api, type HallView } from "./api";
import { Asset, Badge, Btn, CreatureImg, Empty, FitText, Loading, Panel, Stage } from "./ui";

export function Hall({ go }: { go: Go }) {
  const [hall, setHall] = useState<HallView | null>(null);

  useEffect(() => {
    api
      .getHall()
      .then(setHall)
      .catch(() => setHall({ champions: [], top_winners: [], records: [] }));
  }, []);

  if (!hall) return <Loading label="OPENING THE HALL" />;

  const reigning = hall.champions[0] ?? null;
  const rest = hall.champions.slice(1);

  return (
    <div className="hall screen-in">
      <header className="hall__head">
        <p className="eyebrow">EVERY TITLE, KEPT FOREVER</p>
        <h1 className="display display--xl hall__title">HALL OF CHAMPIONS</h1>
      </header>

      <div className="hall__body">
        <Panel title="RECORDS" accent="gold" className="hall__records">
          {hall.records.length ? (
            <div className="cascade records">
              {hall.records.map((r) => (
                <button
                  type="button"
                  className="record"
                  key={r.key}
                  onClick={() => r.creature && go({ name: "codex", id: r.creature.id })}
                  disabled={!r.creature}
                >
                  <Asset slot={`icons/record_${r.key}`} label="" className="record__icon" tint="gold" />
                  <span className="record__text">
                    <span className="record__label">{r.label.toUpperCase()}</span>
                    <FitText className="record__holder">{r.creature?.name || "UNCLAIMED"}</FitText>
                  </span>
                  <span className="record__value num">{r.value}</span>
                </button>
              ))}
            </div>
          ) : (
            <Empty title="No records yet" hint="Build a chimera and the records start filling in." />
          )}
        </Panel>

        <section className="hall__dais">
          {reigning ? (
            <>
              <div className="dais">
                <Asset slot="hall/pedestal" label="" className="dais__pedestal" />
                <Stage creature={reigning} gold caption="RENDER PENDING" className="dais__stage" />
                <Asset slot="trophy/badge_champion" label="" className="dais__badge" />
              </div>
              <div className="dais__plate">
                <p className="dais__eyebrow">REIGNING CHAMPION</p>
                <h2 className="dais__name">{(reigning.name || "CHAMPION").toUpperCase()}</h2>
                <p className="dais__title">{reigning.title || reigning.role}</p>
                <div className="dais__meta">
                  <Badge tone="gold">
                    {reigning.championships} TITLE{reigning.championships === 1 ? "" : "S"}
                  </Badge>
                  <span className="num muted">
                    {reigning.wins}W · {reigning.losses}L
                  </span>
                </div>
                <Btn accent="gold" size="lg" onClick={() => go({ name: "codex", id: reigning.id })}>
                  VIEW RECORD
                </Btn>
              </div>
            </>
          ) : (
            <>
              <div className="dais dais--empty">
                <Asset slot="hall/pedestal" label="" className="dais__pedestal" />
                <Asset slot="trophy/champion_cup" label="" className="dais__cup" />
              </div>
              <div className="dais__plate">
                <p className="dais__eyebrow">THE PLINTH IS EMPTY</p>
                <h2 className="dais__name muted">NO CHAMPION YET</h2>
                <p className="lede">Send eight chimeras into the arena and crown the first one.</p>
              </div>
            </>
          )}
        </section>

        <div className="hall__side">
          <Panel title="TOP WINNERS" accent="cyan" className="hall__winners">
            {hall.top_winners.length ? (
              <ol className="rank">
                {hall.top_winners.map((c, i) => (
                  <li key={c.id}>
                    <button type="button" onClick={() => go({ name: "codex", id: c.id })}>
                      <span className={`rank__n num rank__n--${Math.min(i + 1, 4)}`}>{i + 1}</span>
                      <span className="rank__art">
                        <CreatureImg creature={c} />
                      </span>
                      <FitText className="rank__name">{(c.name || "UNNAMED").toUpperCase()}</FitText>
                      <span className="rank__wins num">
                        <Asset slot="trophy/badge_champion" label="" />
                        {c.wins}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            ) : (
              <Empty title="No battles fought yet" hint="Send eight chimeras into the arena." />
            )}
          </Panel>

          {rest.length > 0 && (
            <Panel title="PAST CHAMPIONS" accent="gold" className="hall__past">
              <div className="pastrow">
                {rest.slice(0, 6).map((c) => (
                  <button
                    type="button"
                    className="past"
                    key={c.id}
                    onClick={() => go({ name: "codex", id: c.id })}
                  >
                    <span className="past__art">
                      <CreatureImg creature={c} />
                    </span>
                    <FitText className="past__name">{(c.name || "UNNAMED").toUpperCase()}</FitText>
                    <span className="past__titles num">{c.championships}×</span>
                  </button>
                ))}
              </div>
            </Panel>
          )}
        </div>
      </div>

      <footer className="hall__foot">
        <Btn accent="ghost" onClick={() => go({ name: "codex" })}>
          BACK TO CODEX
        </Btn>
        <Btn accent="gold" size="lg" icon="icons/nav_arena" onClick={() => go({ name: "arena" })}>
          RUN A TOURNAMENT
        </Btn>
      </footer>
    </div>
  );
}
