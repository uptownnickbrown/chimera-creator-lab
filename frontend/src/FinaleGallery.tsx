/* The finale gallery — every championship painting the arena ever made,
   browsable (Nick, 2026-09-20: "we have all of the prior final battle
   images — why only show three? They're a hallmark cool thing").

   Two surfaces:
     RAIL     a swipeable strip of big 3:2 cards (arrows for the mouse),
              newest first; SEE ALL turns it into a grid.
     VIEWER   one painting full-bleed: swipe / arrows / keys move through the
              set, the plate names the champion and who they beat, and one
              tap opens the champion's codex record.

   Images are gated on nearness (MediaImg lazy) — 53 paintings must not all
   download on arrival — and the viewer preloads its two neighbours so a
   swipe never lands on a blank. */
import { useEffect, useRef, useState } from "react";
import type { Go } from "./App";
import type { CreatureSummary, TournamentView } from "./api";
import { keyArtPath } from "./Finale";
import { Btn, CreatureImg, FitText, MediaImg } from "./ui";

export function finalistsOf(t: TournamentView): {
  champ?: CreatureSummary;
  runnerUp?: CreatureSummary;
} {
  const byId = new Map(t.entrants.map((c) => [c.id, c]));
  const champ = t.champion_id ? byId.get(t.champion_id) : undefined;
  const final = t.rounds[t.rounds.length - 1]?.matches[0];
  const loserId = final ? (final.a === t.champion_id ? final.b : final.a) : null;
  const runnerUp = loserId ? byId.get(loserId) : undefined;
  return { champ, runnerUp };
}

const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

export function dateLabel(iso: string | null | undefined, year = false): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${MONTHS[d.getMonth()]} ${d.getDate()}${year ? `, ${d.getFullYear()}` : ""}`;
}

/** Newest first — the arena's most recent crowning leads. */
export function sortFinales(all: TournamentView[]): TournamentView[] {
  return all
    .filter((t) => t.status === "complete" && keyArtPath(t))
    .sort((a, b) => (b.completed_at ?? "").localeCompare(a.completed_at ?? "") || b.id - a.id);
}

export function FinaleRail({
  finales,
  onOpen,
}: {
  finales: TournamentView[];
  onOpen: (index: number) => void;
}) {
  const [all, setAll] = useState(false);
  const rail = useRef<HTMLDivElement>(null);

  const page = (dir: -1 | 1) => {
    const el = rail.current;
    if (!el) return;
    el.scrollBy({ left: dir * el.clientWidth * 0.86, behavior: "smooth" });
  };

  if (!finales.length) return null;
  return (
    <section className={`gallery${all ? " gallery--grid" : ""}`} aria-label="Famous finales">
      <header className="gallery__head">
        <h2 className="gallery__title">
          FAMOUS FINALES <span className="gallery__count num">{finales.length}</span>
        </h2>
        <div className="gallery__tools">
          {!all && (
            <>
              <button type="button" className="gallery__arrow" onClick={() => page(-1)} aria-label="Earlier finales">
                <i className="gallery__chev gallery__chev--l" />
              </button>
              <button type="button" className="gallery__arrow" onClick={() => page(1)} aria-label="Later finales">
                <i className="gallery__chev gallery__chev--r" />
              </button>
            </>
          )}
          <Btn accent="ghost" size="sm" onClick={() => setAll((v) => !v)}>
            {all ? "BACK TO THE RAIL" : `SEE ALL ${finales.length}`}
          </Btn>
        </div>
      </header>
      <div className={all ? "gallery__grid" : "gallery__rail"} ref={all ? undefined : rail}>
        {finales.map((t, i) => {
          const { champ, runnerUp } = finalistsOf(t);
          return (
            <button
              type="button"
              className="gcard"
              key={t.id}
              onClick={() => onOpen(i)}
              aria-label={`${champ?.name ?? "Champion"} crowned${runnerUp ? ` over ${runnerUp.name}` : ""}`}
            >
              <span className="gcard__art">
                <MediaImg src={keyArtPath(t)} alt="" lazy note="PAINTING" />
              </span>
              <span className="gcard__plate">
                <FitText className="gcard__champ">{(champ?.name ?? "CHAMPION").toUpperCase()}</FitText>
                <span className="gcard__sub">
                  {runnerUp ? `BEAT ${runnerUp.name.toUpperCase()}` : t.name.toUpperCase()}
                </span>
              </span>
              <span className="gcard__date num">{dateLabel(t.completed_at)}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

const SWIPE_PX = 48;

export function FinaleViewer({
  finales,
  index,
  onIndex,
  onClose,
  go,
}: {
  finales: TournamentView[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
  go: Go;
}) {
  const t = finales[index];
  const art = keyArtPath(t);
  const { champ, runnerUp } = finalistsOf(t);
  const touchX = useRef<number | null>(null);
  const prev = index > 0 ? index - 1 : null;
  const next = index < finales.length - 1 ? index + 1 : null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft" && prev !== null) onIndex(prev);
      if (e.key === "ArrowRight" && next !== null) onIndex(next);
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose, onIndex, prev, next]);

  /* Neighbours decode ahead of the swipe. */
  useEffect(() => {
    for (const i of [prev, next]) {
      const src = i === null ? null : keyArtPath(finales[i]);
      if (src) new Image().src = src;
    }
  }, [finales, prev, next]);

  return (
    <div
      className="viewer"
      role="dialog"
      aria-label="Championship finale"
      onTouchStart={(e) => {
        touchX.current = e.touches[0]?.clientX ?? null;
      }}
      onTouchEnd={(e) => {
        const x0 = touchX.current;
        touchX.current = null;
        const x1 = e.changedTouches[0]?.clientX;
        if (x0 === null || x1 === undefined) return;
        const dx = x1 - x0;
        if (dx > SWIPE_PX && prev !== null) onIndex(prev);
        else if (dx < -SWIPE_PX && next !== null) onIndex(next);
      }}
    >
      <div className="viewer__artwrap" key={t.id}>
        <MediaImg src={art} alt={`${champ?.name ?? "Champion"} — the championship final`} note="PAINTING" />
      </div>
      <div className="viewer__scrim" />

      <button type="button" className="viewer__close" onClick={onClose} aria-label="Close">
        <span aria-hidden="true">✕</span>
      </button>
      <button
        type="button"
        className="viewer__arrow viewer__arrow--l"
        onClick={() => prev !== null && onIndex(prev)}
        disabled={prev === null}
        aria-label="Newer finale"
      >
        <i className="gallery__chev gallery__chev--l" />
      </button>
      <button
        type="button"
        className="viewer__arrow viewer__arrow--r"
        onClick={() => next !== null && onIndex(next)}
        disabled={next === null}
        aria-label="Older finale"
      >
        <i className="gallery__chev gallery__chev--r" />
      </button>

      <div className="viewer__plate" key={`plate${t.id}`}>
        <p className="viewer__eyebrow">
          CHAMPIONSHIP FINALE · <span className="num">{index + 1} OF {finales.length}</span>
          {t.completed_at && <span className="viewer__date num"> · {dateLabel(t.completed_at, true)}</span>}
        </p>
        <div className="viewer__pair">
          <span className="viewer__thumb viewer__thumb--champ">
            <CreatureImg creature={champ} />
          </span>
          <h2 className="viewer__name">
            <FitText>{(champ?.name ?? "CHAMPION").toUpperCase()}</FitText>
          </h2>
          {runnerUp && (
            <span className="viewer__thumb viewer__thumb--out">
              <CreatureImg creature={runnerUp} />
            </span>
          )}
        </div>
        <p className="viewer__sub">
          {runnerUp ? (
            <>
              TOOK THE CROWN FROM <b>{runnerUp.name.toUpperCase()}</b>
            </>
          ) : (
            "ARENA CHAMPION"
          )}
        </p>
        <div className="viewer__foot">
          {champ && (
            <Btn accent="gold" icon="icons/tile_codex" onClick={() => go({ name: "codex", id: champ.id })}>
              VIEW CHAMPION
            </Btn>
          )}
          <Btn accent="ghost" onClick={onClose}>
            CLOSE
          </Btn>
        </div>
      </div>
    </div>
  );
}
