/* The Championship Finale — a first-class crafted moment, on par with the
   fusion reveal (Nick, 2026-08-09: "the finals images ROCK... make it very
   satisfying when the image hits").

   Three states, staged:
     WAITING   the champion is crowned but the finals key art (1536x1024, the
               two finalists mid-clash) is still painting (~74s). Its own
               theatre: the finalists face off, energy arcs between them, the
               final's story beats replay underneath. Never a spinner.
     ARRIVED   the art decodes -> a light-bloom iris (never full white), the
               painting scales up FULL-BLEED, the champion plate rides a
               gradient scrim at the bottom, confetti fires WITH the art.
     KEEPSAKE  no art was ever made (oldest data) -> the composited gold
               finale, still celebratory, never a dead card.

   Reachable again from the bracket board and the Hall — the art is a
   keepsake, not a one-time flash. Polling: while final_art is "pending" the
   overlay refreshes the tournament every 5s until the path lands. */
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type CreatureSummary, type TournamentView } from "./api";
import { Btn, CreatureImg, FitText, Stage } from "./ui";

/** `final_art` is "pending" while the key art renders, then a /media path,
    then absent when the lab never made one. Only a path paints. */
export function keyArtPath(t: TournamentView | null | undefined): string | null {
  const art = t?.final_art;
  return typeof art === "string" && (art.startsWith("/") || art.startsWith("http")) ? art : null;
}

const POLL_MS = 5000;
const BEAT_MS = 5200;

export function Finale({
  tournament,
  beats,
  onClose,
  onHall,
}: {
  tournament: TournamentView;
  /** The final battle's story beats — replayed while the painters work. */
  beats?: string[];
  onClose: () => void;
  onHall: () => void;
}) {
  const [t, setT] = useState<TournamentView>(tournament);
  const [decoded, setDecoded] = useState(false);
  const [beat, setBeat] = useState(0);
  const beatsRef = useRef(beats ?? []);

  const art = keyArtPath(t);
  const stillPainting = !art && t.final_art === "pending";
  /* Every match called AND every call right = the player's own championship.
     Deterministic battles make predicting the skill — stamp it in gold. */
  const allMatches = useMemo(() => t.rounds.flatMap((r) => r.matches), [t]);
  const perfect =
    allMatches.length > 0 && allMatches.every((m) => m.prediction_correct === true);
  const perfectStamp = perfect && (
    <div className="finale__perfect">
      ★ PERFECT BRACKET — {allMatches.length} FOR {allMatches.length}! ★
    </div>
  );
  const byId = useMemo(() => new Map(t.entrants.map((c) => [c.id, c])), [t]);
  const champion = t.champion_id ? byId.get(t.champion_id) : null;
  const finalMatch = t.rounds[t.rounds.length - 1]?.matches[0];
  const finalists: (CreatureSummary | undefined)[] = [
    finalMatch?.a ? byId.get(finalMatch.a) : undefined,
    finalMatch?.b ? byId.get(finalMatch.b) : undefined,
  ];

  /* Poll for the key art while it is still painting. */
  useEffect(() => {
    if (!stillPainting) return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api.getTournament(t.id);
        setT(fresh);
      } catch {
        /* transient — keep waiting */
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [stillPainting, t.id]);

  /* Decode the painting off-screen so the reveal never shows a half-loaded
     image — same discipline as the fusion reveal's FINAL RENDER stage. */
  useEffect(() => {
    if (!art) return;
    let dead = false;
    const img = new Image();
    img.onload = () => !dead && setDecoded(true);
    img.onerror = () => !dead && setDecoded(true);
    img.src = art;
    return () => {
      dead = true;
    };
  }, [art]);

  /* The final's story beats replay while the painters work. */
  useEffect(() => {
    if (decoded || beatsRef.current.length < 2) return;
    const timer = setInterval(
      () => setBeat((i) => (i + 1) % beatsRef.current.length),
      BEAT_MS,
    );
    return () => clearInterval(timer);
  }, [decoded]);

  const arrived = Boolean(art) && decoded;
  const waiting = stillPainting || (Boolean(art) && !decoded);

  return (
    <div className="finale" role="dialog" aria-label="Champion crowned">
      {/* Confetti fires WITH the art (or immediately for the keepsake state),
          never before the moment it celebrates. */}
      {(arrived || !waiting) && (
        <div className="ceremony__confetti" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      )}

      {arrived && art ? (
        <>
          <div className="finale__artwrap">
            <img className="finale__art" src={art} alt={`${champion?.name ?? "Champion"} — the championship final`} />
            <div className="finale__scrim" />
          </div>
          <div className="finale__bloom" aria-hidden="true" />
          <div className="finale__plate">
            <p className="eyebrow finale__eyebrow">ARENA CHAMPION</p>
            <h2 className="finale__name">
              <FitText>{(champion?.name ?? "CHAMPION").toUpperCase()}</FitText>
            </h2>
            {champion && (champion.title || champion.role) && (
              <p className="finale__title">{champion.title || champion.role}</p>
            )}
            {perfectStamp}
            <div className="finale__foot">
              <Btn accent="gold" size="lg" icon="icons/tile_hall" onClick={onHall}>
                HALL OF CHAMPIONS
              </Btn>
              <Btn accent="ghost" onClick={onClose}>
                CLOSE
              </Btn>
            </div>
          </div>
        </>
      ) : waiting ? (
        <div className="finale__wait">
          <p className="eyebrow finale__eyebrow">THE BRACKET IS DECIDED</p>
          <h2 className="display display--xl ceremony__title">CHAMPION!</h2>
          <div className="finale__waitname">
            <FitText>{(champion?.name ?? "CHAMPION").toUpperCase()}</FitText>
          </div>

          <div className="finale__clash" aria-hidden="true">
            <span className="finale__fighter">
              <CreatureImg creature={finalists[0]} />
            </span>
            <span className="finale__arc" />
            <span className="finale__fighter finale__fighter--right">
              <CreatureImg creature={finalists[1]} />
            </span>
          </div>

          <p className="finale__painting">
            THE PAINTERS ARE CAPTURING THE FINAL CLASH…
          </p>
          {beatsRef.current.length > 0 && (
            <p className="finale__beat" key={beat}>
              {beatsRef.current[beat % beatsRef.current.length]}
            </p>
          )}
          <div className="finale__foot">
            <Btn accent="ghost" onClick={onClose}>
              PEEK AT THE BRACKET — THE PAINTING WILL WAIT
            </Btn>
          </div>
        </div>
      ) : (
        /* Keepsake fallback: no key art was ever made for this bracket. */
        <div className="ceremony__card">
          <p className="eyebrow">THE BRACKET IS DECIDED</p>
          <h2 className="display display--xl ceremony__title">CHAMPION!</h2>
          <div className="ceremony__stage">
            <Stage creature={champion} gold caption="RENDER PENDING" />
          </div>
          <div className="ceremony__name">{(champion?.name ?? "CHAMPION").toUpperCase()}</div>
          <div className="ceremony__sub">{champion?.title || champion?.role}</div>
          {perfectStamp}
          <div className="ceremony__foot">
            <Btn accent="gold" size="lg" icon="icons/tile_hall" onClick={onHall}>
              HALL OF CHAMPIONS
            </Btn>
            <Btn accent="ghost" onClick={onClose}>
              SEE THE FINAL
            </Btn>
          </div>
        </div>
      )}
    </div>
  );
}
