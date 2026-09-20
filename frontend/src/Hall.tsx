/* Hall of Champions (spec §16) — the reason old creatures still matter.

   Rebuilt 2026-09-20 after Henry's iPad photos: the reigning champion stood
   tiny on a 760px gold disc in a 320px row, three of fifty-three finale
   paintings showed as thin strips, and the page ran three screens tall.

   Now, top to bottom:
     THRONE    a cinematic band — the champion's own crowning painting as the
               backdrop, the champion standing BIG on the gold platform in
               front of it, name plate + titles + VIEW RECORD beside.
     GALLERY   every finale painting, newest first, in a swipeable rail of
               big cards (SEE ALL flips it to a grid); a tap opens the
               full-bleed viewer with swipe / arrows / keys.
     ROW       records, top winners and past champions side by side.
   The throne and the gallery fit the iPad's first screen together. */
import { useEffect, useState } from "react";
import type { Go } from "./App";
import { api, type HallView, type TournamentView } from "./api";
import { keyArtPath } from "./Finale";
import { FinaleRail, FinaleViewer, sortFinales } from "./FinaleGallery";
import { Asset, Badge, Btn, CreatureImg, Empty, FitText, Loading, MediaImg, Panel, Stage } from "./ui";

export function Hall({ go }: { go: Go }) {
  const [hall, setHall] = useState<HallView | null>(null);
  /** Completed tournaments whose finals key art exists — the keepsakes. */
  const [finales, setFinales] = useState<TournamentView[]>([]);
  const [viewerIx, setViewerIx] = useState<number | null>(null);

  useEffect(() => {
    api
      .getHall()
      .then(setHall)
      .catch(() => setHall({ champions: [], top_winners: [], records: [] }));
    api
      .listTournaments()
      .then((all) => setFinales(sortFinales(all)))
      .catch(() => setFinales([]));
  }, []);

  if (!hall) return <Loading label="OPENING THE HALL" />;

  const reigning = hall.champions[0] ?? null;
  const rest = hall.champions.slice(1);
  /* The champion's most recent crowning — the throne's backdrop. */
  const crowningIx = reigning ? finales.findIndex((t) => t.champion_id === reigning.id) : -1;
  const crowning = crowningIx >= 0 ? finales[crowningIx] : null;

  return (
    <div className="hall screen-in">
      <header className="hall__head">
        <p className="eyebrow">EVERY TITLE, KEPT FOREVER</p>
        <h1 className="display display--xl hall__title">HALL OF CHAMPIONS</h1>
      </header>

      {reigning ? (
        <section className={`throne${crowning ? " throne--painted" : ""}`}>
          {crowning && (
            <div className="throne__bg" aria-hidden="true">
              <MediaImg src={keyArtPath(crowning)} alt="" />
            </div>
          )}
          <div className="throne__scrim" aria-hidden="true" />
          <button
            type="button"
            className="throne__stagebtn"
            onClick={() => go({ name: "codex", id: reigning.id })}
            aria-label={`${reigning.name} — view record`}
          >
            <Stage creature={reigning} gold caption="RENDER PENDING" className="throne__stage" />
          </button>
          <div className="throne__plate">
            <p className="throne__eyebrow">REIGNING CHAMPION</p>
            <h2 className="throne__name">
              <FitText>{(reigning.name || "CHAMPION").toUpperCase()}</FitText>
            </h2>
            <p className="throne__title">{reigning.title || reigning.role}</p>
            <div className="throne__meta">
              <Badge tone="gold">
                {reigning.championships} TITLE{reigning.championships === 1 ? "" : "S"}
              </Badge>
              <span className="num throne__record">
                {reigning.wins}W · {reigning.losses}L
              </span>
            </div>
            <div className="throne__actions">
              <Btn accent="gold" size="lg" icon="icons/tile_codex" onClick={() => go({ name: "codex", id: reigning.id })}>
                VIEW RECORD
              </Btn>
              {crowning && (
                <Btn accent="ghost" onClick={() => setViewerIx(crowningIx)}>
                  SEE THE CROWNING
                </Btn>
              )}
            </div>
          </div>
          <Asset slot="trophy/badge_champion" label="" className="throne__badge" />
        </section>
      ) : (
        <section className="throne throne--empty">
          <div className="throne__scrim" aria-hidden="true" />
          <div className="throne__stagebtn">
            <div className="dais dais--empty">
              <Asset slot="hall/pedestal" label="" className="dais__pedestal" />
              <Asset slot="trophy/champion_cup" label="" className="dais__cup" />
            </div>
          </div>
          <div className="throne__plate">
            <p className="throne__eyebrow">THE THRONE IS EMPTY</p>
            <h2 className="throne__name muted">NO CHAMPION YET</h2>
            <p className="lede">Send eight chimeras into the arena and crown the first one.</p>
            <div className="throne__actions">
              <Btn accent="gold" size="lg" icon="icons/nav_arena" onClick={() => go({ name: "arena" })}>
                RUN A TOURNAMENT
              </Btn>
            </div>
          </div>
        </section>
      )}

      <FinaleRail finales={finales} onOpen={setViewerIx} />

      <div className="hall__row">
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
                    <FitText className="record__holder">
                      {r.creature?.name || r.holder || "UNCLAIMED"}
                    </FitText>
                  </span>
                  <span className="record__value num">{r.value}</span>
                </button>
              ))}
            </div>
          ) : (
            <Empty title="No records yet" hint="Build a chimera and the records start filling in." />
          )}
        </Panel>

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

        <Panel title="PAST CHAMPIONS" accent="gold" className="hall__past">
          {rest.length > 0 ? (
            <div className="pastrow">
              {rest.slice(0, 6).map((c) => (
                <button
                  type="button"
                  className="past"
                  key={c.id}
                  onClick={() => go({ name: "codex", id: c.id })}
                >
                  <span className="past__art">
                    <CreatureImg creature={c} lazy />
                  </span>
                  <FitText className="past__name">{(c.name || "UNNAMED").toUpperCase()}</FitText>
                  <span className="past__titles num">{c.championships}×</span>
                </button>
              ))}
            </div>
          ) : (
            <Empty title="One champion so far" hint="Every new winner takes a plaque here." />
          )}
        </Panel>
      </div>

      <footer className="hall__foot">
        <Btn accent="ghost" onClick={() => go({ name: "codex" })}>
          BACK TO CODEX
        </Btn>
        <Btn accent="gold" size="lg" icon="icons/nav_arena" onClick={() => go({ name: "arena" })}>
          RUN A TOURNAMENT
        </Btn>
      </footer>

      {viewerIx !== null && finales[viewerIx] && (
        <FinaleViewer
          finales={finales}
          index={viewerIx}
          onIndex={setViewerIx}
          onClose={() => setViewerIx(null)}
          go={go}
        />
      )}
    </div>
  );
}
