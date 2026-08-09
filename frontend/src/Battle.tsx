/* Screen 5 — the Arena match (spec §17, §7 PREDICT + EXPLAIN,
   art-direction/battle.png).

   Two phases in one frame:
     PREDICT  the arena is painted, both chimeras stand on side platforms
              facing inward, and the two giant plates are the tap targets.
     RESULT   the loser's side dims, the winner takes the laurel, health bars
              run down, three reason cards explain it and the beats play out
              as a short cinematic.

   Resolve is idempotent and permanently cached, so revisiting a finished match
   replays exactly the same fight for free. */
import { useCallback, useEffect, useRef, useState } from "react";
import type { Go } from "./App";
import {
  api,
  type BattleView,
  type BracketMatch,
  type CreatureSummary,
  type TournamentView,
} from "./api";
import {
  Asset,
  Badge,
  Btn,
  CreatureImg,
  FitText,
  Loading,
  Panel,
  RarityBadge,
  Stage,
  envIcon,
  envLabel,
  reasonIcon,
} from "./ui";

const MAX_HEALTH = 1000;
const BEAT_MS = 1400;

/** The battle's own a/b ordering is not the bracket's — always match by id. */
function healthOf(battle: BattleView | null, id?: number): number {
  if (!battle || id === undefined) return MAX_HEALTH;
  if (battle.creature_a_id === id) return battle.health_remaining.a;
  if (battle.creature_b_id === id) return battle.health_remaining.b;
  return MAX_HEALTH;
}

export function Battle({
  go,
  tournamentId,
  matchId,
}: {
  go: Go;
  tournamentId: number;
  matchId: string;
}) {
  const [t, setT] = useState<TournamentView | null>(null);
  const [battle, setBattle] = useState<BattleView | null>(null);
  const [fighting, setFighting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [beat, setBeat] = useState(0);
  const [health, setHealth] = useState(false);
  const [ceremony, setCeremony] = useState(false);
  const beatTimer = useRef<number | null>(null);

  const resolve = useCallback(async () => {
    const out = await api.resolve(tournamentId, matchId);
    setBattle(out.battle);
    setT(out.tournament);
    return out;
  }, [tournamentId, matchId]);

  useEffect(() => {
    let cancelled = false;
    setBattle(null);
    setBeat(0);
    setHealth(false);
    api
      .getTournament(tournamentId)
      .then(async (tour) => {
        if (cancelled) return;
        setT(tour);
        const m = tour.rounds.flatMap((r) => r.matches).find((x) => x.id === matchId);
        // Already fought: replay it straight away (the resolve is cached).
        if (m?.winner != null) await resolve();
      })
      .catch(() => !cancelled && setError("That battle is not ready yet."));
    return () => {
      cancelled = true;
    };
  }, [tournamentId, matchId, resolve]);

  /* Health bars mount full, then run down one frame later so the drop reads
     as damage rather than as a static number. Beats land one at a time. */
  useEffect(() => {
    if (!battle) return;
    const h = setTimeout(() => setHealth(true), 260);
    setBeat(0);
    const step = () => {
      setBeat((n) => {
        if (n >= battle.beats.length - 1) return n; // rest on the knockout
        beatTimer.current = setTimeout(step, BEAT_MS) as unknown as number;
        return n + 1;
      });
    };
    beatTimer.current = setTimeout(step, 900) as unknown as number;
    return () => {
      clearTimeout(h);
      if (beatTimer.current) clearTimeout(beatTimer.current);
    };
  }, [battle]);

  /** Scrubbing the pips takes the cinematic off autoplay. */
  function scrub(i: number) {
    if (beatTimer.current) clearTimeout(beatTimer.current);
    setBeat(i);
  }

  /* A completed bracket earns its ceremony — once, when the final resolves. */
  const isFinal = t ? t.rounds[t.rounds.length - 1]?.matches[0]?.id === matchId : false;
  useEffect(() => {
    if (battle && t?.status === "complete" && isFinal) setCeremony(true);
  }, [battle, t?.status, isFinal]);

  if (error) return <div className="error">{error}</div>;
  if (!t) return <Loading label="OPENING THE ARENA" />;

  const match: BracketMatch | undefined = t.rounds
    .flatMap((r) => r.matches)
    .find((m) => m.id === matchId);
  if (!match) return <div className="error">That match is not on this bracket.</div>;

  const byId = new Map(t.entrants.map((c) => [c.id, c]));
  const a = match.a ? byId.get(match.a) : undefined;
  const b = match.b ? byId.get(match.b) : undefined;
  const environment = battle?.environment ?? match.environment;
  const predicted = battle?.predicted ?? match.predicted;
  const winnerId = battle?.winner_id ?? null;
  const champion = t.champion_id ? byId.get(t.champion_id) : null;
  const nextMatch = t.rounds
    .flatMap((r) => r.matches)
    .find((m) => m.winner === null && m.a !== null && m.b !== null);
  const winsToGo = t.rounds.flatMap((r) => r.matches).filter((m) => m.winner === null).length;

  async function predict(id: number) {
    setT(await api.predict(tournamentId, matchId, id));
  }

  async function fight() {
    setFighting(true);
    try {
      await resolve();
    } catch {
      setError("That battle could not run.");
    }
    setFighting(false);
  }

  const showResult = Boolean(battle);

  return (
    <div className="battle screen-in">
      <header className="battle__head">
        <div className="battle__title">
          <h1 className="display">{showResult ? "ARENA BATTLE RESULT" : "ARENA SHOWDOWN"}</h1>
        </div>
        <div className="battle__env">
          <Asset slot={envIcon(environment)} label="" className="battle__envicon" />
          {envLabel(environment)}
        </div>
      </header>

      <section
        className={`battle__arena${showResult ? " is-resolved" : ""}`}
        style={{ backgroundImage: `url(/assets/env/${environment}.png)` }}
      >
        <div className="battle__arenaveil" />

        <Corner
          creature={a}
          side="left"
          winner={winnerId === a?.id}
          loser={showResult && winnerId !== a?.id}
          picked={predicted === a?.id}
          resolved={showResult}
          health={healthOf(battle, a?.id)}
          animate={health}
          onPick={!showResult && a ? () => predict(a.id) : undefined}
        />

        <div className="battle__center">
          {showResult && battle ? (
            <>
              {predicted !== null && (
                <div className="verdict">
                  <div className="verdict__label">YOU PICKED</div>
                  <FitText className="verdict__pick">
                    {(byId.get(predicted)?.name ?? "—").toUpperCase()}
                  </FitText>
                  <div className={`verdict__result${battle.prediction_correct ? " is-correct" : " is-wrong"}`}>
                    {battle.prediction_correct ? "CORRECT!" : "NOT THIS TIME"}
                  </div>
                </div>
              )}
              <div className="winner">
                <div className="winner__label">★ WINNER ★</div>
                <div className="winner__wreath">
                  {/* one painted wreath, cropped into the two flanking branches
                      the mock draws around the winner's name */}
                  <span className="winner__branch winner__branch--l">
                    <Asset slot="trophy/laurel" label="" />
                  </span>
                  <FitText className="winner__name">
                    {(byId.get(battle.winner_id)?.name ?? "—").toUpperCase()}
                  </FitText>
                  <span className="winner__branch winner__branch--r">
                    <Asset slot="trophy/laurel" label="" />
                  </span>
                </div>
                <div className="winner__confidence num">
                  CONFIDENCE {Math.round(battle.confidence * 100)}%
                  {battle.cached && <Badge tone="muted">REPLAY</Badge>}
                </div>
              </div>
            </>
          ) : (
            <div className="predict">
              <p className="predict__ask">WHO DO YOU THINK WINS?</p>
              <div className="predict__pair">
                {[a, b].map((c, i) =>
                  c ? (
                    <button
                      key={c.id}
                      type="button"
                      className={`pickplate${predicted === c.id ? " is-picked" : ""}`}
                      onClick={() => predict(c.id)}
                    >
                      <span className="pickplate__art">
                        <CreatureImg creature={c} />
                      </span>
                      <FitText className="pickplate__name">{(c.name || "UNNAMED").toUpperCase()}</FitText>
                      <span className="pickplate__state">
                        {predicted === c.id ? "YOUR PICK" : "TAP TO PICK"}
                      </span>
                    </button>
                  ) : (
                    <div className="pickplate is-empty" key={i}>
                      <span className="pickplate__name muted">TBD</span>
                    </div>
                  ),
                )}
              </div>
              <Btn
                accent="gold"
                size="xl"
                icon="icons/nav_arena"
                onClick={fight}
                disabled={!a || !b || fighting}
                sub={predicted ? "PICK LOCKED IN" : "PICKING IS OPTIONAL"}
              >
                {fighting ? "FIGHTING…" : "FIGHT!"}
              </Btn>
            </div>
          )}
        </div>

        <Corner
          creature={b}
          side="right"
          winner={winnerId === b?.id}
          loser={showResult && winnerId !== b?.id}
          picked={predicted === b?.id}
          resolved={showResult}
          health={healthOf(battle, b?.id)}
          animate={health}
          onPick={!showResult && b ? () => predict(b.id) : undefined}
        />
      </section>

      {showResult && battle && (
        <section className="battle__why">
          <h2 className="battle__whytitle">
            WHY {(byId.get(battle.winner_id)?.name ?? "THE WINNER").toUpperCase()} WON
          </h2>
          <div className="reasons">
            {battle.reasons.map((r, i) => (
              <div className="reason" key={r.icon + r.title} style={{ animationDelay: `${240 + i * 130}ms` }}>
                <Asset
                  slot={reasonIcon(r.icon, environment)}
                  label=""
                  className="reason__icon"
                  tint={i === 0 ? "purple" : i === 2 ? "teal" : undefined}
                />
                <div className="reason__title">{r.title.toUpperCase()}</div>
                <div className="reason__blurb">{r.blurb}</div>
              </div>
            ))}
          </div>

          {/* the fight as a short cinematic: one beat at a time, tappable pips */}
          <div className="cine">
            <span className="cine__label">HOW IT PLAYED OUT</span>
            <p className="cine__line" key={beat}>
              {battle.beats[Math.min(beat, battle.beats.length - 1)]}
            </p>
            <div className="cine__pips">
              {battle.beats.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  className={`cine__pip${i === beat ? " is-on" : ""}${i < beat ? " is-past" : ""}`}
                  onClick={() => scrub(i)}
                  aria-label={`Beat ${i + 1}`}
                />
              ))}
            </div>
          </div>
        </section>
      )}

      <aside className="battle__rail">
        <Panel title="TOURNAMENT BRACKET" accent="cyan" className="battle__tree">
          <div className="tree">
            {t.rounds.map((round) => (
              <div className="tree__round" key={round.name}>
                <div className="tree__title">{round.name.toUpperCase()}</div>
                {round.matches.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    className={`tree__match${m.id === matchId ? " is-current" : ""}`}
                    onClick={() => m.a && m.b && go({ name: "arena", tid: t.id, matchId: m.id })}
                    disabled={!m.a || !m.b}
                  >
                    {[m.a, m.b].map((cid, side) => {
                      const c = cid ? byId.get(cid) : null;
                      return (
                        <span
                          key={side}
                          className={`tree__side${c && m.winner === c.id ? " is-winner" : ""}${
                            c && m.winner !== null && m.winner !== c.id ? " is-out" : ""
                          }`}
                        >
                          <span className="tree__art">
                            <CreatureImg creature={c} />
                          </span>
                          <FitText className="tree__name">{c ? (c.name || "UNNAMED").toUpperCase() : "TBD"}</FitText>
                          {c && m.winner === c.id && <span className="tree__tick">✓</span>}
                        </span>
                      );
                    })}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="CHAMPION TRACKER" accent="gold" className="battle__tracker">
          {champion ? (
            <div className="tracker">
              <Asset slot="trophy/champion_cup" label="" className="tracker__cup" />
              <FitText className="tracker__name">{(champion.name || "CHAMPION").toUpperCase()}</FitText>
              <div className="tracker__label">ARENA CHAMPION</div>
              <Btn accent="gold" size="sm" onClick={() => go({ name: "hall" })}>
                HALL OF CHAMPIONS
              </Btn>
            </div>
          ) : (
            <div className="tracker">
              <Asset slot="trophy/champion_cup" label="" className="tracker__cup tracker__cup--dim" />
              <div className="tracker__count num">{winsToGo}</div>
              <div className="tracker__label">
                BATTLE{winsToGo === 1 ? "" : "S"} LEFT TO CROWN A CHAMPION
              </div>
              <div className="tracker__stars">
                {t.rounds.map((r) => (
                  <i key={r.name} className={r.matches.every((m) => m.winner !== null) ? "is-on" : ""} />
                ))}
              </div>
            </div>
          )}
        </Panel>
      </aside>

      <footer className="battle__foot">
        {nextMatch ? (
          <Btn
            accent="purple"
            size="lg"
            icon="icons/nav_arena"
            onClick={() => go({ name: "arena", tid: t.id, matchId: nextMatch.id })}
          >
            NEXT BATTLE
          </Btn>
        ) : (
          <Btn accent="gold" size="lg" icon="icons/tile_hall" onClick={() => go({ name: "hall" })}>
            HALL OF CHAMPIONS
          </Btn>
        )}
        <Btn accent="cyan" onClick={() => go({ name: "arena", tid: t.id })}>
          VIEW BRACKET
        </Btn>
        <Btn accent="ghost" onClick={() => go({ name: "codex" })}>
          BACK TO CODEX
        </Btn>
      </footer>

      {ceremony && champion && (
        <Ceremony
          champion={champion}
          art={keyArt(t)}
          onClose={() => setCeremony(false)}
          onHall={() => go({ name: "hall" })}
        />
      )}
    </div>
  );
}

/** `final_art` is "pending" while the championship key art renders, then a
    /media path, then absent when the lab never made one. Only a path paints. */
function keyArt(t: TournamentView): string | null {
  const art = t.final_art;
  return typeof art === "string" && (art.startsWith("/") || art.startsWith("http")) ? art : null;
}

function Corner({
  creature,
  side,
  winner,
  loser,
  picked,
  resolved,
  health,
  animate,
  onPick,
}: {
  creature?: CreatureSummary;
  side: "left" | "right";
  winner: boolean;
  loser: boolean;
  picked: boolean;
  resolved: boolean;
  health: number;
  animate: boolean;
  onPick?: () => void;
}) {
  const pct = Math.max(0, Math.min(100, ((animate ? health : MAX_HEALTH) / MAX_HEALTH) * 100));
  // Before the bell everyone is on full health — a red bar would lie about it.
  const tone = !resolved ? "cyan" : winner ? "green" : "red";
  return (
    <div className={`corner corner--${side}${winner ? " is-winner" : ""}${loser ? " is-out" : ""}`}>
      <div className="corner__id">
        <span className="corner__badge">
          <CreatureImg creature={creature} />
        </span>
        <div className="corner__text">
          <FitText className="corner__name">{(creature?.name || "TBD").toUpperCase()}</FitText>
          <div className="corner__meta">
            {creature && <RarityBadge rarity={creature.rarity} />}
            {picked && <Badge tone="purple">YOUR PICK</Badge>}
            {winner && <Badge tone="gold">WINNER</Badge>}
          </div>
        </div>
      </div>

      <button
        type="button"
        className="corner__stage"
        onClick={onPick}
        disabled={!onPick}
        aria-label={onPick ? `Pick ${creature?.name}` : undefined}
      >
        {/* the right-hand fighter is mirrored so the two face each other */}
        <Stage creature={creature} gold={winner} flip={side === "right"} caption="RENDER PENDING" />
      </button>

      <div className="corner__health">
        <Asset
          slot="icons/endurance"
          label=""
          className="corner__heart"
          tint={tone === "cyan" ? undefined : (tone as "green" | "red")}
        />
        <div className="meter" data-tone={tone}>
          <div className="meter__fill" style={{ width: `${pct}%` }} />
        </div>
        <span className="num">
          {animate ? health : MAX_HEALTH} / {MAX_HEALTH}
        </span>
      </div>
    </div>
  );
}

function Ceremony({
  champion,
  art,
  onClose,
  onHall,
}: {
  champion: CreatureSummary;
  art: string | null;
  onClose: () => void;
  onHall: () => void;
}) {
  return (
    <div className="ceremony" role="dialog" aria-label="Champion crowned">
      <div className="ceremony__confetti" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="ceremony__card">
        <p className="eyebrow">THE BRACKET IS DECIDED</p>
        <h2 className="display display--xl ceremony__title">CHAMPION!</h2>
        <div className="ceremony__stage">
          {art ? (
            <img className="ceremony__art" src={art} alt={`${champion.name} championship art`} />
          ) : (
            <Stage creature={champion} gold caption="RENDER PENDING" />
          )}
        </div>
        <div className="ceremony__name">{(champion.name || "CHAMPION").toUpperCase()}</div>
        <div className="ceremony__sub">{champion.title || champion.role}</div>
        <div className="ceremony__foot">
          <Btn accent="gold" size="lg" icon="icons/tile_hall" onClick={onHall}>
            HALL OF CHAMPIONS
          </Btn>
          <Btn accent="ghost" onClick={onClose}>
            SEE THE FINAL
          </Btn>
        </div>
      </div>
    </div>
  );
}
