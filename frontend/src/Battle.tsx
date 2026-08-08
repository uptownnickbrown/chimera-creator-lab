/* Screen 5 — Battle Result (spec §17, §7 EXPLAIN). Resolve is idempotent and
   permanently cached, so re-opening a finished match replays the same fight. */
import { useEffect, useState } from "react";
import type { Go } from "./App";
import { api, type BattleView, type CreatureSummary, type TournamentView } from "./api";
import { Asset, Badge, Btn, Loading, Meter, Panel } from "./ui";

const MAX_HEALTH = 1000;

export function Battle({
  go,
  tournamentId,
  matchId,
}: {
  go: Go;
  tournamentId: number;
  matchId: string;
}) {
  const [battle, setBattle] = useState<BattleView | null>(null);
  const [t, setT] = useState<TournamentView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .resolve(tournamentId, matchId)
      .then((out) => {
        if (cancelled) return;
        setBattle(out.battle);
        setT(out.tournament);
      })
      .catch(() => !cancelled && setError("That battle is not ready yet."));
    return () => {
      cancelled = true;
    };
  }, [tournamentId, matchId]);

  if (error) return <div className="error">{error}</div>;
  if (!battle || !t) return <Loading label="RESOLVING THE MATCHUP" />;

  const byId = new Map(t.entrants.map((c) => [c.id, c]));
  const a = byId.get(battle.creature_a_id);
  const b = byId.get(battle.creature_b_id);
  const nextMatch = t.rounds
    .flatMap((r) => r.matches)
    .find((m) => m.winner === null && m.a !== null && m.b !== null);
  const champion = t.champion_id ? byId.get(t.champion_id) : null;
  const winsToGo = t.rounds.flatMap((r) => r.matches).filter((m) => m.winner === null).length;

  return (
    <div className="battle">
      <header className="battle__head">
        <h1 className="display">ARENA BATTLE RESULT</h1>
        <div className="battle__env">
          <Asset slot={`environments/${battle.environment}`} label="" className="battle__envart" />
          {battle.environment.replace(/_/g, " ").toUpperCase()}
        </div>
      </header>

      <section className="battle__main">
        <Fighter creature={a} health={battle.health_remaining.a} winner={battle.winner_id === a?.id} side="left" />

        <div className="battle__center">
          {battle.predicted !== null && (
            <div className="verdict">
              <div className="verdict__label">YOU PICKED</div>
              <div className="verdict__pick">{byId.get(battle.predicted)?.name.toUpperCase() ?? "—"}</div>
              <div className={`verdict__result${battle.prediction_correct ? " is-correct" : " is-wrong"}`}>
                {battle.prediction_correct ? "CORRECT!" : "NOT THIS TIME"}
              </div>
            </div>
          )}

          <div className="winner">
            <div className="winner__label">WINNER</div>
            <div className="winner__name">
              {(byId.get(battle.winner_id)?.name ?? "—").toUpperCase()}
            </div>
            <div className="winner__confidence muted num">
              CONFIDENCE {Math.round(battle.confidence * 100)}%
            </div>
            {battle.cached && <Badge tone="muted">REPLAY</Badge>}
          </div>
        </div>

        <Fighter creature={b} health={battle.health_remaining.b} winner={battle.winner_id === b?.id} side="right" />

        <aside className="battle__bracket">
          <Panel title="TOURNAMENT BRACKET" accent="cyan">
            {t.rounds.map((round) => (
              <div className="mini" key={round.name}>
                <div className="mini__title">{round.name.toUpperCase()}</div>
                {round.matches.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    className={`mini__match${m.id === matchId ? " is-current" : ""}`}
                    onClick={() => m.winner && go({ name: "arena", tid: t.id, matchId: m.id })}
                    disabled={!m.winner}
                  >
                    <span>{m.a ? byId.get(m.a)?.name ?? "TBD" : "TBD"}</span>
                    <span className="muted">vs</span>
                    <span>{m.b ? byId.get(m.b)?.name ?? "TBD" : "TBD"}</span>
                  </button>
                ))}
              </div>
            ))}
          </Panel>

          <Panel title="CHAMPION TRACKER" accent="gold">
            {champion ? (
              <div className="tracker">
                <Asset slot={`creatures/${champion.id}`} label={champion.name} className="tracker__art" />
                <div className="tracker__name">{champion.name.toUpperCase()}</div>
                <div className="tracker__label">ARENA CHAMPION</div>
              </div>
            ) : (
              <div className="tracker">
                <div className="tracker__count num">{winsToGo}</div>
                <div className="tracker__label">
                  BATTLE{winsToGo === 1 ? "" : "S"} LEFT TO CROWN A CHAMPION
                </div>
              </div>
            )}
          </Panel>
        </aside>
      </section>

      <section className="battle__why">
        <h2 className="battle__whytitle">
          WHY {(byId.get(battle.winner_id)?.name ?? "THE WINNER").toUpperCase()} WON
        </h2>
        <div className="reasons">
          {battle.reasons.map((r) => (
            <div className="reason" key={r.icon + r.title}>
              <Asset slot={`icons/reason_${r.icon}`} label="" className="reason__icon" />
              <div className="reason__title">{r.title.toUpperCase()}</div>
              <div className="reason__blurb">{r.blurb}</div>
            </div>
          ))}
        </div>

        <Panel title="HOW IT PLAYED OUT" accent="purple">
          <p className="narrative">{battle.narrative}</p>
          <ol className="beats">
            {battle.beats.map((beat, i) => (
              <li key={i}>{beat}</li>
            ))}
          </ol>
        </Panel>
      </section>

      <footer className="battle__foot">
        {nextMatch ? (
          <Btn
            accent="purple"
            size="lg"
            onClick={() => go({ name: "arena", tid: t.id, matchId: nextMatch.id })}
          >
            NEXT BATTLE
          </Btn>
        ) : (
          <Btn accent="gold" size="lg" onClick={() => go({ name: "hall" })}>
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
    </div>
  );
}

function Fighter({
  creature,
  health,
  winner,
  side,
}: {
  creature?: CreatureSummary;
  health: number;
  winner: boolean;
  side: "left" | "right";
}) {
  return (
    <div className={`bfighter bfighter--${side}${winner ? " is-winner" : ""}`}>
      <div className="bfighter__id">
        <Asset
          slot={creature ? `creatures/${creature.id}` : "ui/tbd"}
          label={creature?.name ?? "TBD"}
          className="bfighter__badge"
        />
        <div>
          <div className="bfighter__name">{(creature?.name ?? "—").toUpperCase()}</div>
          <div className="bfighter__role muted">{creature?.role ?? ""}</div>
        </div>
      </div>
      <Asset
        slot={creature ? `creatures/${creature.id}` : "ui/tbd"}
        label={creature?.name ?? "TBD"}
        className="bfighter__art"
      />
      <div className="bfighter__health">
        <span className="bfighter__hlabel">HEALTH</span>
        <Meter value={health} max={MAX_HEALTH} tone={winner ? "green" : "red"} />
        <span className="num">
          {health} / {MAX_HEALTH}
        </span>
      </div>
    </div>
  );
}
