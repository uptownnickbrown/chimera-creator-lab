/* Arena — single active tournament (spec 2026-08-09).

   There is never a choice between in-flight brackets: #/arena goes straight
   into the current bracket with the NEXT MATCH called out huge, with a PAST
   CHALLENGES shelf of finished tournaments underneath (champion thumb + name,
   tap to revisit read-only, finale key art included). No current bracket ->
   the eight-entrant setup. POST /tournaments 409s while one is active; the
   setup answers with "finish or abandon?".

   GET /tournaments/current answers with the live TournamentView (or JSON
   null); the tournament-list walk stays as a fallback for an older server. */
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Go } from "./App";
import { ApiError, api, type CodexSort, type CreatureSummary, type TournamentView } from "./api";
import { Finale, keyArtPath } from "./Finale";
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
  useMashGuard,
} from "./ui";

const ENTRANTS = 8;

/** The roster's quick filters: the Codex sorts, in the Codex's words. */
const ROSTER_SORTS: { key: CodexSort; label: string }[] = [
  { key: "newest", label: "ALL" },
  { key: "favorites", label: "FAVORITES" },
  { key: "winners", label: "WINNERS" },
  { key: "biggest", label: "BIGGEST" },
  { key: "fastest", label: "FASTEST" },
  { key: "strongest", label: "STRONGEST" },
];

export function Bracket({ go, tournamentId }: { go: Go; tournamentId?: number }) {
  if (tournamentId) return <BracketBoard go={go} tournamentId={tournamentId} />;
  return <ArenaLanding go={go} />;
}

// -- landing: straight into the one live bracket, or into setup ---------------

/** The current bracket, via the new contract with a list-derived fallback. */
async function findCurrent(): Promise<number | null> {
  try {
    const cur = await api.getCurrentTournament();
    return cur?.id ?? null;
  } catch {
    try {
      const all = await api.listTournaments();
      return all.find((t) => t.status !== "complete")?.id ?? null;
    } catch {
      return null;
    }
  }
}

function ArenaLanding({ go }: { go: Go }) {
  const [state, setState] = useState<
    { kind: "loading" } | { kind: "current"; tid: number } | { kind: "setup" }
  >({ kind: "loading" });

  useEffect(() => {
    let dead = false;
    findCurrent().then((tid) => {
      if (dead) return;
      setState(tid ? { kind: "current", tid } : { kind: "setup" });
    });
    return () => {
      dead = true;
    };
  }, []);

  if (state.kind === "loading") return <Loading label="OPENING THE ARENA" />;
  if (state.kind === "current")
    return <BracketBoard go={go} tournamentId={state.tid} landing />;
  return <Setup go={go} />;
}

// -- past challenges shelf ------------------------------------------------------

function championOf(t: TournamentView): CreatureSummary | undefined {
  return t.entrants.find((c) => c.id === t.champion_id);
}

function PastShelf({ go, exceptId }: { go: Go; exceptId?: number }) {
  const [past, setPast] = useState<TournamentView[]>([]);

  useEffect(() => {
    api
      .listTournaments()
      .then((all) =>
        setPast(all.filter((t) => t.status === "complete" && t.id !== exceptId)),
      )
      .catch(() => setPast([]));
  }, [exceptId]);

  if (!past.length) return null;
  return (
    <Panel title="PAST CHALLENGES" accent="gold" className="shelf">
      <div className="shelf__row">
        {past.slice(0, 8).map((t) => {
          const champ = championOf(t);
          return (
            <button
              key={t.id}
              type="button"
              className="shelf__item"
              onClick={() => go({ name: "arena", tid: t.id })}
              title={`${t.name} — champion ${champ?.name ?? "unknown"}`}
            >
              <span className="shelf__art">
                <CreatureImg creature={champ} />
              </span>
              <FitText className="shelf__champ">{(champ?.name ?? "CHAMPION").toUpperCase()}</FitText>
              <span className="shelf__name">{t.name}</span>
            </button>
          );
        })}
      </div>
    </Panel>
  );
}

// -- setup --------------------------------------------------------------------

/** One roster card. Memoised so a pick re-renders two cards, not 130. */
const SetupCard = memo(function SetupCard({
  c,
  index,
  onToggle,
}: {
  c: CreatureSummary;
  /** Position in the picked list, -1 when not picked. */
  index: number;
  onToggle: (id: number) => void;
}) {
  return (
    <CreatureCard
      creature={c}
      selected={index >= 0}
      onClick={() => onToggle(c.id)}
      corner={index >= 0 ? <Badge tone="cyan">{index + 1}</Badge> : undefined}
    />
  );
});

function Setup({ go }: { go: Go }) {
  const [roster, setRoster] = useState<CreatureSummary[] | null>(null);
  const [picked, setPicked] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  /** POST answered 409 — one bracket is already live. */
  const [conflict, setConflict] = useState(false);
  /* 130 chimeras in one grid was a scroll past every card to reach START.
     The same sorts and search as the Codex cut it to the ones Henry means
     ("my favorites", "the winners", "the big ones"); picks survive a filter
     change — they live on the ids, not the visible list. */
  const [sort, setSort] = useState<CodexSort>("newest");
  const [query, setQuery] = useState("");
  const loadSeq = useRef(0);

  useEffect(() => {
    const seq = ++loadSeq.current;
    api
      .listCreatures(sort)
      .then((rows) => seq === loadSeq.current && setRoster(rows))
      .catch(() => seq === loadSeq.current && setRoster((r) => r ?? []));
  }, [sort]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? (roster ?? []).filter((c) => (c.name || "").toLowerCase().includes(q)) : roster ?? [];
  }, [roster, query]);

  /* A burst of taps on one card is one pick, never pick-unpick-pick. */
  const guard = useMashGuard();
  const toggle = useCallback(
    (id: number) => {
      if (!guard(`c:${id}`)) return;
      setError(null);
      setPicked((prev) =>
        prev.includes(id)
          ? prev.filter((x) => x !== id)
          : prev.length >= ENTRANTS
            ? prev
            : [...prev, id],
      );
    },
    [guard],
  );

  /** Eight at random from whatever is on screen — "random eight winners". */
  function randomEight() {
    if (!roster) return;
    const pool = [...(visible.length >= ENTRANTS ? visible : roster)];
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
      if (e instanceof ApiError && e.status === 409) {
        setConflict(true);
      } else {
        setError(e instanceof ApiError ? e.message : "The arena is closed right now.");
      }
      setBusy(false);
    }
  }

  async function abandonAndStart() {
    setBusy(true);
    setError(null);
    try {
      const tid = await findCurrent();
      if (tid) await api.deleteTournament(tid);
      setConflict(false);
      const t = await api.createTournament(picked);
      go({ name: "arena", tid: t.id });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That bracket would not step aside.");
      setBusy(false);
    }
  }

  async function goCurrent() {
    const tid = await findCurrent();
    if (tid) go({ name: "arena", tid });
    else setConflict(false);
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
        {/* The actions come FIRST in the flow: on the iPad this bar sticks to
            the top of the page while the roster scrolls under it, so START is
            one tap away from anywhere. Desktop keeps it in the right column. */}
        <aside className="arena__aside">
          <Btn
            accent="purple"
            size="lg"
            icon="icons/dice"
            onClick={randomEight}
            disabled={roster.length < ENTRANTS}
          >
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

        <Panel
          title={`ENTRANTS — ${picked.length} OF ${ENTRANTS}`}
          accent="teal"
          className="arena__roster"
          action={
            <div className="roster__tools">
              <div className="codex__sorts" role="group" aria-label="Filter the roster">
                {ROSTER_SORTS.map((o) => (
                  <button
                    key={o.key}
                    type="button"
                    className={`sortpill${sort === o.key ? " is-active" : ""}`}
                    onClick={() => setSort(o.key)}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
              <label className="search">
                <Asset slot="icons/search" label="" className="search__icon" />
                <input
                  type="search"
                  value={query}
                  placeholder="Find…"
                  onChange={(e) => setQuery(e.target.value)}
                  aria-label="Search your chimeras"
                />
              </label>
            </div>
          }
        >
          {sort === "newest" && !query.trim() && roster.length < ENTRANTS ? (
            <Empty
              title={`You need ${ENTRANTS} chimeras to run a bracket`}
              hint={`You have ${roster.length}. Build a few more in the Fusion Lab.`}
            />
          ) : visible.length ? (
            <div className="arena__rosterscroll">
              <div className="grid">
                {visible.map((c) => (
                  <SetupCard key={c.id} c={c} index={picked.indexOf(c.id)} onToggle={toggle} />
                ))}
              </div>
            </div>
          ) : (
            <Empty
              title={query.trim() ? `Nothing matches “${query.trim()}”` : "Nothing here yet"}
              hint={query.trim() ? "Try another name." : "Try ALL, or build more in the Fusion Lab."}
            />
          )}
        </Panel>

        <PastShelf go={go} />
      </div>

      {conflict && (
        <div className="conflict" role="dialog" aria-label="A bracket is already running">
          <div className="panel panel--gold conflict__card">
            <div className="panel__body">
              <h2 className="conflict__ask">FINISH OR ABANDON YOUR CURRENT BRACKET?</h2>
              <p className="conflict__line">
                Only one tournament runs at a time — one bracket is still in play.
              </p>
              <div className="conflict__row">
                <Btn accent="teal" size="lg" onClick={goCurrent}>
                  GO FINISH IT
                </Btn>
                <Btn accent="ghost" onClick={abandonAndStart} disabled={busy}>
                  ABANDON IT — START FRESH
                </Btn>
              </div>
              <Btn accent="ghost" size="sm" onClick={() => setConflict(false)}>
                NEVER MIND
              </Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// -- the board ----------------------------------------------------------------

function BracketBoard({
  go,
  tournamentId,
  landing,
}: {
  go: Go;
  tournamentId: number;
  /** Landed here from #/arena — show the PAST CHALLENGES shelf. */
  landing?: boolean;
}) {
  const [t, setT] = useState<TournamentView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [finale, setFinale] = useState(false);
  /** ABANDON failsafe: quiet, two-tap. */
  const [confirmAbandon, setConfirmAbandon] = useState(false);
  const [abandonError, setAbandonError] = useState<string | null>(null);

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
  /* The server names the next match; the client-side scan is the fallback for
     an older server (and the two agree by construction). */
  const next =
    all.find((m) => m.id === t.next_match_id) ??
    all.find((m) => m.winner === null && m.a !== null && m.b !== null);
  const correct = all.filter((m) => m.prediction_correct === true).length;
  const called = all.filter((m) => m.prediction_correct !== null).length;
  const nextA = next?.a ? byId.get(next.a) : null;
  const nextB = next?.b ? byId.get(next.b) : null;
  const hasFinaleArt = Boolean(keyArtPath(t)) || t.final_art === "pending";

  async function abandon() {
    try {
      await api.deleteTournament(t!.id);
      go({ name: "arena" });
    } catch {
      setAbandonError("The bracket would not fold. Try again in a moment.");
    }
  }

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
              <span
                className={`arena__calls num${
                  called === all.length && correct === called ? " is-perfect" : ""
                }`}
              >
                MY CALLS: {correct}/{called}
              </span>
            )}
          </div>
        </div>
      </header>

      {/* THE NEXT MATCH, called out huge — the one thing to do next. */}
      {next && (
        <button
          type="button"
          className="nextmatch"
          onClick={() => go({ name: "arena", tid: t.id, matchId: next.id })}
        >
          <span className="nextmatch__key">NEXT MATCH</span>
          <span className="nextmatch__pair">
            <span className="nextmatch__fighter">
              <span className="nextmatch__art">
                <CreatureImg creature={nextA} />
              </span>
              <FitText className="nextmatch__name">
                {(nextA?.name ?? "TBD").toUpperCase()}
              </FitText>
            </span>
            <span className="nextmatch__vs">VS</span>
            <span className="nextmatch__fighter">
              <span className="nextmatch__art">
                <CreatureImg creature={nextB} />
              </span>
              <FitText className="nextmatch__name">
                {(nextB?.name ?? "TBD").toUpperCase()}
              </FitText>
            </span>
          </span>
          <span className="nextmatch__env">
            <Asset slot={envIcon(next.environment)} label="" className="match__envicon" />
            {envLabel(next.environment)}
          </span>
          <span className="nextmatch__cta">PREDICT &amp; FIGHT</span>
        </button>
      )}

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
                      style={{ backgroundImage: `url(/assets/env/${m.environment}_card.webp)` }}
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
                  {hasFinaleArt && (
                    <Btn accent="gold" size="sm" onClick={() => setFinale(true)}>
                      SEE THE FINALE
                    </Btn>
                  )}
                  <Btn accent="ghost" size="sm" onClick={() => go({ name: "hall" })}>
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

      {landing && <PastShelf go={go} exceptId={t.id} />}

      <footer className="arena__foot">
        {t.status !== "complete" &&
          (confirmAbandon ? (
            <div className="release release--row">
              <p className="release__ask">Abandon this bracket? Its battles are lost.</p>
              <Btn accent="ghost" size="sm" onClick={() => setConfirmAbandon(false)}>
                KEEP PLAYING
              </Btn>
              <button type="button" className="release__go" onClick={abandon}>
                YES — ABANDON
              </button>
            </div>
          ) : (
            <button type="button" className="release__quiet" onClick={() => setConfirmAbandon(true)}>
              ABANDON BRACKET
            </button>
          ))}
        {abandonError && <div className="error">{abandonError}</div>}
        <Btn accent="ghost" onClick={() => go({ name: "codex" })}>
          BACK TO CODEX
        </Btn>
        {champion && (
          <Btn accent="gold" size="lg" icon="icons/tile_hall" onClick={() => go({ name: "hall" })}>
            HALL OF CHAMPIONS
          </Btn>
        )}
      </footer>

      {finale && (
        <Finale tournament={t} onClose={() => setFinale(false)} onHall={() => go({ name: "hall" })} />
      )}
    </div>
  );
}
