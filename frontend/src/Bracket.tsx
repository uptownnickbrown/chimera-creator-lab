/* Arena — tournament setup and the bracket itself (spec §15, §7 PREDICT).
   Eight entrants, quarterfinals to championship, one prediction per match. */
import { useCallback, useEffect, useState } from "react";
import type { Go } from "./App";
import { ApiError, api, type CreatureSummary, type TournamentView } from "./api";
import { Asset, Badge, Btn, CreatureCard, CreatureImg, Empty, Loading, Panel } from "./ui";

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
    <div className="arena">
      <header className="arena__head">
        <h1 className="display">BATTLE BRACKET</h1>
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
          ) : (
            <Empty
              title={`You need ${ENTRANTS} chimeras to run a bracket`}
              hint={`You have ${roster.length}. Build a few more in the Fusion Lab.`}
            />
          )}
        </Panel>

        <aside className="arena__aside">
          <Panel title="PAST TOURNAMENTS" accent="gold">
            {history.length ? (
              <ul className="tlist">
                {history.map((t) => (
                  <li key={t.id}>
                    <button type="button" onClick={() => go({ name: "arena", tid: t.id })}>
                      <span>{t.name}</span>
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
            RANDOM TOURNAMENT
          </Btn>
          <Btn
            accent="gold"
            size="lg"
            onClick={start}
            disabled={picked.length !== ENTRANTS || busy}
            sub={picked.length === ENTRANTS ? "QUARTERFINALS BEGIN" : `PICK ${ENTRANTS - picked.length} MORE`}
          >
            START TOURNAMENT
          </Btn>
          <Btn accent="ghost" onClick={() => go({ name: "hall" })}>
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
  const [busy, setBusy] = useState<string | null>(null);
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

  async function predict(matchId: string, pickId: number) {
    setBusy(matchId);
    try {
      setT(await api.predict(tournamentId, matchId, pickId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not lock that pick in.");
    }
    setBusy(null);
  }

  async function fight(matchId: string) {
    setBusy(matchId);
    try {
      await api.resolve(tournamentId, matchId);
      go({ name: "arena", tid: tournamentId, matchId });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That battle could not run.");
      setBusy(null);
    }
  }

  if (error) return <div className="error">{error}</div>;
  if (!t) return <Loading label="LOADING BRACKET" />;

  const byId = new Map(t.entrants.map((c) => [c.id, c]));
  const champion = t.champion_id ? byId.get(t.champion_id) : null;
  const remaining = t.rounds.flatMap((r) => r.matches).filter((m) => m.winner === null).length;

  return (
    <div className="arena">
      <header className="arena__head">
        <h1 className="display">{t.name.toUpperCase()}</h1>
        <div className="arena__status">
          <Badge tone={t.status === "complete" ? "gold" : "cyan"}>{t.status.toUpperCase()}</Badge>
          <span className="muted">
            {t.status === "complete"
              ? `Champion: ${champion?.name ?? "—"}`
              : `${remaining} battle${remaining === 1 ? "" : "s"} to go`}
          </span>
        </div>
      </header>

      <div className="board">
        {t.rounds.map((round, ri) => (
          <div className="board__round" key={round.name}>
            <h2 className="board__title">{round.name.toUpperCase()}</h2>
            {round.matches.map((m) => {
              const a = m.a ? byId.get(m.a) : null;
              const b = m.b ? byId.get(m.b) : null;
              const open = !!a && !!b && m.winner === null;
              return (
                <div className={`match${m.winner ? " is-done" : ""}`} key={m.id}>
                  <div className="match__env">
                    <Asset slot={`env/${m.environment}`} label="" className="match__envart" />
                    {m.environment.replace(/_/g, " ").toUpperCase()}
                  </div>

                  {[a, b].map((c, side) => (
                    <button
                      key={side}
                      type="button"
                      className={
                        "fighter" +
                        (c && m.winner === c.id ? " is-winner" : "") +
                        (c && m.predicted === c.id ? " is-picked" : "")
                      }
                      onClick={() => c && open && predict(m.id, c.id)}
                      disabled={!c || !open || busy === m.id}
                    >
                      <CreatureImg creature={c} className="fighter__art" />
                      <span className="fighter__name">{c ? c.name.toUpperCase() : "TBD"}</span>
                      {c && m.predicted === c.id && <Badge tone="purple">YOUR PICK</Badge>}
                      {c && m.winner === c.id && <Badge tone="gold">WINNER</Badge>}
                    </button>
                  ))}

                  <div className="match__foot">
                    {m.winner ? (
                      <Btn
                        accent="ghost"
                        onClick={() => go({ name: "arena", tid: t.id, matchId: m.id })}
                      >
                        VIEW RESULT
                      </Btn>
                    ) : (
                      <Btn
                        accent={ri === 0 ? "cyan" : "teal"}
                        onClick={() => fight(m.id)}
                        disabled={!open || busy === m.id}
                        sub={m.predicted ? "PICK LOCKED IN" : "PICK A WINNER FIRST (OPTIONAL)"}
                      >
                        {busy === m.id ? "FIGHTING…" : "FIGHT"}
                      </Btn>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>

      <footer className="arena__foot">
        <Btn accent="ghost" onClick={() => go({ name: "arena" })}>
          ALL TOURNAMENTS
        </Btn>
        <Btn accent="ghost" onClick={() => go({ name: "codex" })}>
          BACK TO CODEX
        </Btn>
        {champion && (
          <Btn accent="gold" size="lg" onClick={() => go({ name: "hall" })}>
            HALL OF CHAMPIONS
          </Btn>
        )}
      </footer>
    </div>
  );
}
