/* Arena — tournament setup and the bracket board (spec §15, §7 PREDICT).
   Eight entrants, quarterfinals to championship. Predicting and fighting live
   on the match screen (Battle.tsx); the board is the map you tap into. */
import { useCallback, useEffect, useState } from "react";
import type { Go } from "./App";
import { ApiError, api, type CreatureSummary, type TournamentView } from "./api";
import {
  Asset,
  Badge,
  Btn,
  CreatureCard,
  CreatureImg,
  Empty,
  FitText,
  Loading,
  Panel,
  envIcon,
  envLabel,
} from "./ui";

const ENTRANTS = 8;

export function Bracket({ go, tournamentId }: { go: Go; tournamentId?: number }) {
  if (tournamentId) return <BracketBoard go={go} tournamentId={tournamentId} />;
  return <Setup go={go} />;
}

// -- setup --------------------------------------------------------------------

function Setup({ go }: { go: Go }) {
  const [roster, setRoster] = useState<CreatureSummary[] | null>(null);
  const [history, setHistory] = useState<TournamentView[]>([]);
  const [picked, setPicked] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listCreatures("newest").then(setRoster).catch(() => setRoster([]));
    api.listTournaments().then(setHistory).catch(() => setHistory([]));
  }, []);

  function toggle(id: number) {
    setError(null);
    setPicked((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : prev.length >= ENTRANTS
          ? prev
          : [...prev, id],
    );
  }

  function randomEight() {
    if (!roster) return;
    const pool = [...roster];
    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    setPicked(pool.slice(0, ENTRANTS).map((c) => c.id));
  }

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const t = await api.createTournament(picked);
      go({ name: "arena", tid: t.id });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The arena is closed right now.");
      setBusy(false);
    }
  }

  if (!roster) return <Loading label="OPENING THE ARENA" />;

  return (
    <div className="arena screen-in">
      <header className="arena__head">
        <h1 className="display display--xl">BATTLE BRACKET</h1>
        <p className="lede">
          Choose eight chimeras. Predict every match. One of them walks out as champion.
        </p>
      </header>

      <div className="arena__setup">
        <Panel
          title={`ENTRANTS — ${picked.length} OF ${ENTRANTS}`}
          accent="teal"
          className="arena__roster"
        >
          {roster.length >= ENTRANTS ? (
            <div className="arena__rosterscroll">
              <div className="grid">
                {roster.map((c) => {
                  const index = picked.indexOf(c.id);
                  return (
                    <CreatureCard
                      key={c.id}
                      creature={c}
                      selected={index >= 0}
                      onClick={() => toggle(c.id)}
                      corner={index >= 0 ? <Badge tone="cyan">{index + 1}</Badge> : undefined}
                    />
                  );
                })}
              </div>
            </div>
          ) : (
            <Empty
              title={`You need ${ENTRANTS} chimeras to run a bracket`}
              hint={`You have ${roster.length}. Build a few more in the Fusion Lab.`}
            />
          )}
        </Panel>

        <aside className="arena__aside">
          <Panel title="PAST TOURNAMENTS" accent="gold" className="arena__history">
            {history.length ? (
              <ul className="tlist">
                {history.map((t) => (
                  <li key={t.id}>
                    <button type="button" onClick={() => go({ name: "arena", tid: t.id })}>
                      <Asset
                        slot={t.status === "complete" ? "trophy/badge_champion" : "icons/nav_arena"}
                        label=""
                        className="tlist__icon"
                      />
                      <FitText className="tlist__name">{t.name}</FitText>
                      <Badge tone={t.status === "complete" ? "gold" : "cyan"}>
                        {t.status.toUpperCase()}
                      </Badge>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty title="No tournaments yet" />
            )}
          </Panel>
          <Btn accent="ghost" onClick={randomEight} disabled={roster.length < ENTRANTS}>
            RANDOM EIGHT
          </Btn>
          <Btn
            accent="gold"
            size="lg"
            icon="icons/nav_arena"
            onClick={start}
            disabled={picked.length !== ENTRANTS || busy}
            sub={picked.length === ENTRANTS ? "QUARTERFINALS BEGIN" : `PICK ${ENTRANTS - picked.length} MORE`}
          >
            START TOURNAMENT
          </Btn>
          <Btn accent="ghost" icon="icons/tile_hall" onClick={() => go({ name: "hall" })}>
            HALL OF CHAMPIONS
          </Btn>
          {error && <div className="error">{error}</div>}
        </aside>
      </div>
    </div>
  );
}

// -- the board ----------------------------------------------------------------

function BracketBoard({ go, tournamentId }: { go: Go; tournamentId: number }) {
  const [t, setT] = useState<TournamentView | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setT(await api.getTournament(tournamentId));
    } catch {
      setError("That tournament could not be found.");
    }
  }, [tournamentId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <div className="error">{error}</div>;
  if (!t) return <Loading label="LOADING BRACKET" />;

  const byId = new Map(t.entrants.map((c) => [c.id, c]));
  const champion = t.champion_id ? byId.get(t.champion_id) : null;
  const all = t.rounds.flatMap((r) => r.matches);
  const remaining = all.filter((m) => m.winner === null).length;
  const next = all.find((m) => m.winner === null && m.a !== null && m.b !== null);
  const correct = all.filter((m) => m.prediction_correct === true).length;
  const called = all.filter((m) => m.prediction_correct !== null).length;

  return (
    <div className="arena screen-in">
      <header className="arena__head arena__head--board">
        <div>
          <h1 className="display">{t.name.toUpperCase()}</h1>
          <div className="arena__status">
            <Badge tone={t.status === "complete" ? "gold" : "cyan"}>{t.status.toUpperCase()}</Badge>
            <span className="muted">
              {t.status === "complete"
                ? `Champion: ${champion?.name ?? "—"}`
                : `${remaining} battle${remaining === 1 ? "" : "s"} to go`}
            </span>
            {called > 0 && (
              <span className="arena__calls num">
                PREDICTIONS {correct}/{called}
              </span>
            )}
          </div>
        </div>
        {next && (
          <Btn
            accent="teal"
            size="lg"
            icon="icons/nav_arena"
            onClick={() => go({ name: "arena", tid: t.id, matchId: next.id })}
            sub="STEP INTO THE ARENA"
          >
            NEXT BATTLE
          </Btn>
        )}
      </header>

      <div className="board">
        {t.rounds.map((round, ri) => (
          <div className={`board__round board__round--${ri}`} key={round.name}>
            <h2 className="board__title">{round.name.toUpperCase()}</h2>
            <div className="board__matches">
              {round.matches.map((m) => {
                const a = m.a ? byId.get(m.a) : null;
                const b = m.b ? byId.get(m.b) : null;
                const open = !!a && !!b && m.winner === null;
                return (
                  <button
                    type="button"
                    className={`match${m.winner ? " is-done" : ""}${open ? " is-open" : ""}`}
                    key={m.id}
                    onClick={() => (a && b ? go({ name: "arena", tid: t.id, matchId: m.id }) : undefined)}
                    disabled={!a || !b}
                  >
                    <span
                      className="match__bg"
                      style={{ backgroundImage: `url(/assets/env/${m.environment}_card.png)` }}
                    />
                    <span className="match__env">
                      <Asset slot={envIcon(m.environment)} label="" className="match__envicon" />
                      {envLabel(m.environment)}
                    </span>

                    {[a, b].map((c, side) => (
                      <span
                        key={side}
                        className={
                          "fighter" +
                          (c && m.winner === c.id ? " is-winner" : "") +
                          (c && m.winner !== null && m.winner !== c.id ? " is-out" : "") +
                          (c && m.predicted === c.id ? " is-picked" : "")
                        }
                      >
                        <span className="fighter__art">
                          <CreatureImg creature={c} />
                        </span>
                        <FitText className="fighter__name">{c ? (c.name || "UNNAMED").toUpperCase() : "TBD"}</FitText>
                        {c && m.winner === c.id && (
                          <Asset slot="trophy/badge_champion" label="" className="fighter__crown" />
                        )}
                        {c && m.predicted === c.id && m.winner === null && <Badge tone="purple">PICK</Badge>}
                      </span>
                    ))}

                    <span className="match__cta">
                      {m.winner ? "VIEW RESULT" : open ? "PREDICT & FIGHT" : "WAITING"}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}

        <div className="board__round board__round--crown">
          <h2 className="board__title">CHAMPION</h2>
          <div className="board__matches">
            <div className={`crown${champion ? " is-crowned" : ""}`}>
              {champion ? (
                <>
                  <Asset slot="trophy/champion_cup" label="" className="crown__cup" />
                  <FitText className="crown__name">{(champion.name || "CHAMPION").toUpperCase()}</FitText>
                  <Btn accent="gold" size="sm" onClick={() => go({ name: "hall" })}>
                    HALL OF CHAMPIONS
                  </Btn>
                </>
              ) : (
                <>
                  <Asset slot="trophy/champion_cup" label="" className="crown__cup crown__cup--dim" />
                  <span className="crown__name muted">TBD</span>
                  <span className="crown__hint num">{remaining} TO GO</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <footer className="arena__foot">
        <Btn accent="ghost" onClick={() => go({ name: "arena" })}>
          ALL TOURNAMENTS
        </Btn>
        <Btn accent="ghost" onClick={() => go({ name: "codex" })}>
          BACK TO CODEX
        </Btn>
        {champion && (
          <Btn accent="gold" size="lg" icon="icons/tile_hall" onClick={() => go({ name: "hall" })}>
            HALL OF CHAMPIONS
          </Btn>
        )}
      </footer>
    </div>
  );
}
