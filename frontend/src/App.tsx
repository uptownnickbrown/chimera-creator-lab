/* Shell: top nav + hash routing. No router library (Agora convention).

   #/home  #/lab  #/reveal/<id>  #/codex[/<id>]  #/arena[/<tid>[/<matchId>]]  #/hall */
import { useCallback, useEffect, useState } from "react";
import { api, type ProfileView } from "./api";
import { Asset } from "./ui";
import { Home } from "./Home";
import { FusionLab } from "./FusionLab";
import { Reveal } from "./Reveal";
import { Codex } from "./Codex";
import { Bracket } from "./Bracket";
import { Battle } from "./Battle";
import { Hall } from "./Hall";

export type Route =
  | { name: "home" }
  | { name: "lab" }
  | { name: "reveal"; id: number }
  | { name: "codex"; id?: number }
  | { name: "arena"; tid?: number; matchId?: string }
  | { name: "hall" };

export type Go = (route: Route) => void;

export function hashFor(route: Route): string {
  switch (route.name) {
    case "reveal":
      return `#/reveal/${route.id}`;
    case "codex":
      return route.id ? `#/codex/${route.id}` : "#/codex";
    case "arena":
      if (route.tid && route.matchId) return `#/arena/${route.tid}/${route.matchId}`;
      return route.tid ? `#/arena/${route.tid}` : "#/arena";
    default:
      return `#/${route.name}`;
  }
}

export function parseHash(hash: string): Route {
  const [head, ...rest] = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  switch (head) {
    case "lab":
      return { name: "lab" };
    case "reveal":
      return { name: "reveal", id: Number(rest[0]) || 0 };
    case "codex":
      return { name: "codex", id: rest[0] ? Number(rest[0]) : undefined };
    case "arena":
      return {
        name: "arena",
        tid: rest[0] ? Number(rest[0]) : undefined,
        matchId: rest[1],
      };
    case "hall":
      return { name: "hall" };
    default:
      return { name: "home" };
  }
}

const NAV: { label: string; route: Route; matches: Route["name"][] }[] = [
  { label: "HOME", route: { name: "home" }, matches: ["home"] },
  { label: "FUSION LAB", route: { name: "lab" }, matches: ["lab", "reveal"] },
  { label: "CODEX", route: { name: "codex" }, matches: ["codex"] },
  { label: "ARENA", route: { name: "arena" }, matches: ["arena", "hall"] },
];

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(location.hash));
  const [profile, setProfile] = useState<ProfileView | null>(null);

  useEffect(() => {
    const onHash = () => setRoute(parseHash(location.hash));
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);

  const go: Go = useCallback((next) => {
    const target = hashFor(next);
    if (location.hash === target) setRoute(next);
    else location.hash = target;
  }, []);

  const refreshProfile = useCallback(async () => {
    try {
      setProfile(await api.getProfile());
    } catch {
      setProfile(null); // API asleep — the shell still renders.
    }
  }, []);

  useEffect(() => {
    refreshProfile();
  }, [refreshProfile, route.name]);

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <Asset slot="ui/logo" label="CC" className="brand__mark" />
          <div>
            <div className="brand__name">CHIMERA CREATOR</div>
            <div className="brand__sub">NEON LAB</div>
          </div>
        </div>

        <nav className="nav">
          {NAV.map((item) => (
            <button
              key={item.label}
              type="button"
              className={`nav__tab${item.matches.includes(route.name) ? " is-active" : ""}`}
              onClick={() => go(item.route)}
            >
              <Asset slot={`icons/nav_${item.label.split(" ")[0].toLowerCase()}`} label="" className="nav__icon" />
              {item.label}
            </button>
          ))}
        </nav>

        <div className="player">
          <div className="player__chips">
            <span className="chip">
              <Asset slot="icons/xp" label="XP" className="chip__icon" />
              <b className="num">{profile?.xp ?? 0}</b>
            </span>
            <span className="chip">
              <Asset slot="icons/creatures" label="C" className="chip__icon" />
              <b className="num">{profile?.total_creatures ?? 0}</b>
            </span>
          </div>
          <Asset slot="ui/avatar" label={profile?.name ?? "?"} className="player__avatar" />
          <div className="player__id">
            <div className="player__name">{(profile?.name ?? "player").toUpperCase()}</div>
            <div className="player__level">LVL {profile?.level ?? 1}</div>
          </div>
        </div>
      </header>

      <main className="screen">
        {route.name === "home" && <Home go={go} profile={profile} />}
        {route.name === "lab" && <FusionLab go={go} />}
        {route.name === "reveal" && <Reveal go={go} creatureId={route.id} />}
        {route.name === "codex" && <Codex go={go} selectedId={route.id} />}
        {route.name === "arena" && !route.matchId && (
          <Bracket go={go} tournamentId={route.tid} />
        )}
        {route.name === "arena" && route.matchId && route.tid && (
          <Battle go={go} tournamentId={route.tid} matchId={route.matchId} />
        )}
        {route.name === "hall" && <Hall go={go} />}
      </main>
    </div>
  );
}
