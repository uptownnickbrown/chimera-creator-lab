/* Screen 5 — the Arena match (spec §17, §7 PREDICT + EXPLAIN,
   art-direction/battle.png).

   Two phases in one frame:
     PREDICT  the arena is painted, both chimeras stand grounded facing
              inward (no pedestal discs — contact shadows keep their feet on
              the floor), and the two giant plates are the tap targets.
     RESULT   the loser's side dims, the winner takes the laurel, health bars
              run down, and the STORY takes center stage: a large readable
              card that plays the beats one at a time — tap to advance, sized
              so a parent can read it aloud. Reason cards explain the call.

   Tapping either fighter's name chip (any phase) or its render (result
   phase) opens the scout modal: hero, five stats, moves — codex language,
   one tap anywhere to close. Nobody leaves the battle to scout.

   Resolve is idempotent and permanently cached, so revisiting a finished
   match replays exactly the same fight for free. When the championship match
   resolves, the Finale takes over and the generated key art is the hero
   moment. */
import { useCallback, useEffect, useRef, useState } from "react";
import type { Go } from "./App";
import {
  api,
  getLibraryCached,
  type BattleView,
  type BracketMatch,
  type CreatureDetail,
  type CreatureSummary,
  type TournamentView,
} from "./api";
import { Finale } from "./Finale";
import {
  Asset,
  Badge,
  Btn,
  CreatureImg,
  FitText,
  Loading,
  MoveCards,
  Panel,
  RarityBadge,
  Stage,
  StatRow,
  envIcon,
  envLabel,
  reasonIcon,
} from "./ui";

const MAX_HEALTH = 1000;
/** Slow enough to read aloud; a tap advances immediately. */
const BEAT_MS = 5200;

/** The battle's own a/b ordering is not the bracket's — always match by id. */
function healthOf(battle: BattleView | null, id?: number): number {
  if (!battle || id === undefined) return MAX_HEALTH;
  if (battle.creature_a_id === id) return battle.health_remaining.a;
  if (battle.creature_b_id === id) return battle.health_remaining.b;
  return MAX_HEALTH;
}

/** Confidence in kid language — "66%" is noise to an eight-year-old. */
function verdictWord(confidence: number): string {
  if (confidence >= 0.8) return "CLEAR WINNER!";
  if (confidence >= 0.65) return "STRONG WIN!";
  return "CLOSE ONE!";
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
  /** A failed FIGHT keeps the predict UI on screen — never the dead-end error. */
  const [fightError, setFightError] = useState<string | null>(null);
  const [beat, setBeat] = useState(0);
  const [health, setHealth] = useState(false);
  const [ceremony, setCeremony] = useState(false);
  /** Scout modal: which creature id is open (null = closed). */
  const [scoutId, setScoutId] = useState<number | null>(null);
  const beatTimer = useRef<number | null>(null);
  /* A kid alternating taps between the two pick plates fires overlapping
     POSTs; only the newest response may set state or the pick shown can be
     one he did not tap last. */
  const predictSeq = useRef(0);

  /* The arena's one-line intel card (spec §9): the environment's kid-readable
     properties are the reasoning fuel for the prediction. Already client-side
     via the cached library — this just surfaces it. */
  const [envBlurbs, setEnvBlurbs] = useState<Map<string, string> | null>(null);
  useEffect(() => {
    let dead = false;
    getLibraryCached()
      .then((lib) => !dead && setEnvBlurbs(new Map(lib.environments.map((e) => [e.slug, e.blurb]))))
      .catch(() => {}); // no intel card, no harm
    return () => {
      dead = true;
    };
  }, []);

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
    // The opening sentence gets its full read too: settle-in time for the
    // winner banner PLUS a whole beat — the 1400 alone was the bug that
    // flashed beat 0 for 1.4s while eyes were still on the banner.
    beatTimer.current = setTimeout(step, 1400 + BEAT_MS) as unknown as number;
    return () => {
      clearTimeout(h);
      if (beatTimer.current) clearTimeout(beatTimer.current);
    };
  }, [battle]);

  /** A tap on the story card (or a pip) takes the cinematic off autoplay. */
  function scrub(i: number) {
    if (beatTimer.current) clearTimeout(beatTimer.current);
    setBeat(Math.max(0, Math.min(i, (battle?.beats.length ?? 1) - 1)));
  }

  /* A completed bracket earns its finale — once, when the final resolves. */
  const isFinal = t ? t.rounds[t.rounds.length - 1]?.matches[0]?.id === matchId : false;
  useEffect(() => {
    if (battle && t?.status === "complete" && isFinal) setCeremony(true);
  }, [battle, t?.status, isFinal]);

  /* Error dead-ends get a door: a 7-year-old should never be stranded with
     one sentence and no button. */
  const errorScreen = (msg: string) => (
    <div className="battle__error">
      <div className="error">{msg}</div>
      <Btn accent="cyan" onClick={() => go({ name: "arena", tid: tournamentId })}>
        BACK TO THE BRACKET
      </Btn>
    </div>
  );

  if (error) return errorScreen(error);
  if (!t) return <Loading label="OPENING THE ARENA" />;

  const match: BracketMatch | undefined = t.rounds
    .flatMap((r) => r.matches)
    .find((m) => m.id === matchId);
  if (!match) return errorScreen("That match is not on this bracket.");

  const byId = new Map(t.entrants.map((c) => [c.id, c]));
  const a = match.a ? byId.get(match.a) : undefined;
  const b = match.b ? byId.get(match.b) : undefined;
  const environment = battle?.environment ?? match.environment;
  const predicted = battle?.predicted ?? match.predicted;
  const winnerId = battle?.winner_id ?? null;
  const champion = t.champion_id ? byId.get(t.champion_id) : null;
  // Never point NEXT BATTLE at the match already on screen — a dead button.
  const nextMatch = t.rounds
    .flatMap((r) => r.matches)
    .find((m) => m.id !== matchId && m.winner === null && m.a !== null && m.b !== null);
  const winsToGo = t.rounds.flatMap((r) => r.matches).filter((m) => m.winner === null).length;

  async function predict(id: number) {
    if (fighting) return; // the pick is locked once FIGHT is in flight
    const seq = ++predictSeq.current;
    try {
      const out = await api.predict(tournamentId, matchId, id);
      if (seq === predictSeq.current) setT(out);
    } catch {
      /* the previous pick stands — tapping again retries */
    }
  }

  async function fight() {
    setFighting(true);
    setFightError(null);
    try {
      await resolve();
    } catch {
      setFightError("The battle fizzled — tap FIGHT to try again!");
    }
    setFighting(false);
  }

  const showResult = Boolean(battle);
  const lastBeat = battle ? battle.beats.length - 1 : 0;

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
        style={{ backgroundImage: `url(/assets/env/${environment}.webp)` }}
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
          onScout={a ? () => setScoutId(a.id) : undefined}
        />

        <div className="battle__center">
          {showResult && battle ? (
            <>
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
                <div className="winner__confidence">
                  <span className="winner__word">{verdictWord(battle.confidence)}</span>
                  {/* A right call celebrates the earned XP (fresh fights only —
                      replays already paid out); a wrong one gets drama, not a
                      cold red stamp. */}
                  {predicted !== null &&
                    (battle.prediction_correct ? (
                      <Badge tone="green">
                        {battle.cached ? "YOU CALLED IT!" : "YOU CALLED IT! +25 XP"}
                      </Badge>
                    ) : (
                      <Badge tone="red">
                        {battle.confidence < 0.65
                          ? "SO CLOSE — NEARLY A TIE!"
                          : "THE LAB SAW IT DIFFERENTLY"}
                      </Badge>
                    ))}
                  {battle.cached && <Badge tone="muted">REPLAY</Badge>}
                </div>
              </div>

              {/* THE BATTLE STORY — the main event after the winner banner:
                  one beat at a time, big type, tap to turn the page. */}
              <button type="button" className="story" onClick={() => scrub(beat + 1)}>
                <span className="story__key">THE BATTLE STORY</span>
                <span className="story__line" key={beat}>
                  {battle.beats[Math.min(beat, lastBeat)]}
                </span>
                <span className="story__row">
                  <span className="story__pips">
                    {battle.beats.map((_, i) => (
                      <i
                        key={i}
                        className={`story__pip${i === beat ? " is-on" : ""}${i < beat ? " is-past" : ""}`}
                      />
                    ))}
                  </span>
                  <span className="story__hint">
                    {beat < lastBeat ? "TAP FOR WHAT HAPPENS NEXT" : "THE END"}
                  </span>
                </span>
              </button>
            </>
          ) : (
            <div className="predict">
              <p className="predict__ask">WHO DO YOU THINK WINS?</p>
              {envBlurbs?.get(environment) && (
                <p className="predict__intel">
                  <Asset slot={envIcon(environment)} label="" className="predict__intel-icon" />
                  <span>
                    <b>{envLabel(environment)}</b> — {envBlurbs.get(environment)}
                  </span>
                </p>
              )}
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
                sub={predicted ? "PICK LOCKED IN" : "WHO'S YOUR PICK?"}
              >
                {fighting ? "FIGHTING…" : "FIGHT!"}
              </Btn>
              {fightError && <div className="error">{fightError}</div>}
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
          onScout={b ? () => setScoutId(b.id) : undefined}
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
              <Btn accent="gold" size="sm" onClick={() => setCeremony(true)}>
                SEE THE FINALE
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
      </footer>

      {scoutId !== null && <ScoutModal creatureId={scoutId} onClose={() => setScoutId(null)} />}

      {ceremony && (
        <Finale
          tournament={t}
          beats={isFinal ? battle?.beats : undefined}
          onClose={() => setCeremony(false)}
          onHall={() => go({ name: "hall" })}
        />
      )}
    </div>
  );
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
  onScout,
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
  onScout?: () => void;
}) {
  const pct = Math.max(0, Math.min(100, ((animate ? health : MAX_HEALTH) / MAX_HEALTH) * 100));
  // Before the bell everyone is on full health — a red bar would lie about it.
  const tone = !resolved ? "cyan" : winner ? "green" : "red";
  /* In the predict phase the big render is the PICK target; after the bell it
     becomes a scout target. The name chip scouts in every phase. */
  const stageAction = onPick ?? (resolved ? onScout : undefined);
  return (
    <div className={`corner corner--${side}${winner ? " is-winner" : ""}${loser ? " is-out" : ""}`}>
      <button type="button" className="corner__id" onClick={onScout} disabled={!onScout} title={creature ? `Scout ${creature.name}` : undefined}>
        <span className="corner__badge">
          <CreatureImg creature={creature} />
        </span>
        <span className="corner__text">
          <FitText className="corner__name">{(creature?.name || "TBD").toUpperCase()}</FitText>
          <span className="corner__meta">
            {creature && <RarityBadge rarity={creature.rarity} />}
            {picked && <Badge tone="purple">YOUR PICK</Badge>}
            {winner && <Badge tone="gold">WINNER</Badge>}
          </span>
        </span>
      </button>

      <button
        type="button"
        className="corner__stage"
        onClick={stageAction}
        disabled={!stageAction}
        aria-label={onPick ? `Pick ${creature?.name}` : creature ? `Scout ${creature.name}` : undefined}
      >
        {/* No pedestal discs in the arena: grounded plain stage, feet on a
            contact shadow. The right-hand fighter mirrors to face inward. */}
        <Stage plain creature={creature} gold={winner} flip={side === "right"} caption="RENDER PENDING" />
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

/** The in-battle scout card: the fighter's codex record without leaving the
    match. One tap anywhere closes it. */
function ScoutModal({ creatureId, onClose }: { creatureId: number; onClose: () => void }) {
  const [detail, setDetail] = useState<CreatureDetail | null>(null);

  useEffect(() => {
    let dead = false;
    setDetail(null);
    api
      .getCreature(creatureId)
      .then((d) => !dead && setDetail(d))
      .catch(() => !dead && setDetail(null));
    return () => {
      dead = true;
    };
  }, [creatureId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="scout" role="dialog" aria-label="Fighter stats" onClick={onClose}>
      <div className="panel panel--cyan scout__card">
        {detail ? (
          <div className="panel__body scout__body">
            <header className="detail__head">
              <div className="detail__id">
                <h2 className="detail__name">
                  <FitText>{(detail.name || "UNNAMED").toUpperCase()}</FitText>
                </h2>
                <div className="detail__badges">
                  <RarityBadge rarity={detail.rarity} />
                  <span className="muted">{detail.title || detail.role}</span>
                </div>
              </div>
              <span className="scout__record num">
                {detail.wins}W · {detail.losses}L
              </span>
            </header>
            <div className="scout__stage">
              <Stage plain creature={detail} caption="RENDER PENDING" />
            </div>
            <StatRow compact stats={detail.core_stats} />
            {detail.abilities.length > 0 && <MoveCards abilities={detail.abilities} />}
            <span className="scout__hint">TAP ANYWHERE TO CLOSE</span>
          </div>
        ) : (
          <div className="panel__body">
            <Loading label="SCOUTING" />
          </div>
        )}
      </div>
    </div>
  );
}
