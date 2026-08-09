/* Shell: the painted ground, the top bar and hash routing. No router library
   (Agora convention).

   #/home  #/lab  #/reveal/<id>  #/codex[/<id>]  #/arena[/<tid>[/<matchId>]]  #/hall

   The lab plate is the app ground for every screen (UI_STANDARD §Layer stack);
   arena routes swap it for the arena plate, the hall warms it to gold. */
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

const NAV: { label: string; icon: string; route: Route; matches: Route["name"][] }[] = [
  { label: "HOME", icon: "icons/nav_home", route: { name: "home" }, matches: ["home"] },
  { label: "FUSION LAB", icon: "icons/nav_fusion", route: { name: "lab" }, matches: ["lab", "reveal"] },
  { label: "CODEX", icon: "icons/nav_codex", route: { name: "codex" }, matches: ["codex"] },
  { label: "ARENA", icon: "icons/nav_arena", route: { name: "arena" }, matches: ["arena", "hall"] },
];

function sceneFor(route: Route): string {
  if (route.name === "arena") return "arena";
  if (route.name === "hall") return "gold";
  return "lab";
}

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

  const key = `${route.name}:${"id" in route ? route.id : ""}${"tid" in route ? route.tid : ""}${
    "matchId" in route ? route.matchId : ""
  }`;

  return (
    <>
      <div className="ground" data-scene={sceneFor(route)} aria-hidden="true">
        <div className="ground__plate" />
        <div className="ground__veil" />
        <div className="ground__tint" />
        <div className="motes" />
        <div className="motes motes--far" />
      </div>

      <div className="shell">
        <header className="topbar">
          <button type="button" className="brand" onClick={() => go({ name: "home" })}>
            <Asset slot="ui/logo" label="" className="brand__mark" />
            <span className="brand__text">
              <span className="brand__name">CHIMERA</span>
              <span className="brand__sub">CREATOR LAB</span>
            </span>
          </button>

          <nav className="nav">
            {NAV.map((item) => (
              <button
                key={item.label}
                type="button"
                className={`nav__tab${item.matches.includes(route.name) ? " is-active" : ""}`}
                onClick={() => go(item.route)}
              >
                <Asset slot={item.icon} label="" className="nav__icon" />
                {item.label}
              </button>
            ))}
          </nav>

          <div className="player">
            <span
              className="player__badge"
              title={`${200 - ((profile?.xp ?? 0) % 200)} XP to level ${(profile?.level ?? 1) + 1}`}
            >
              <svg className="player__ring" viewBox="0 0 58 58" aria-hidden="true">
                <circle className="player__ring-track" cx="29" cy="29" r="26" />
                <circle
                  className="player__ring-fill"
                  cx="29"
                  cy="29"
                  r="26"
                  strokeDasharray={`${(((profile?.xp ?? 0) % 200) / 200) * 163.36} 163.36`}
                />
              </svg>
              <span className="player__avatar">
                <Asset slot="ui/avatar" label="" />
              </span>
            </span>
            <div className="player__id">
              <div className="player__name">{(profile?.name ?? "player").toUpperCase()}</div>
              <div className="player__level">LVL {profile?.level ?? 1}</div>
            </div>
          </div>
        </header>

        <main className="screen" key={key}>
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
    </>
  );
}
