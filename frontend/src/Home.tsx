/* Screen 1 — Home / Welcome (spec §17). Decide what to do within seconds. */
import { useEffect, useState } from "react";
import type { Go } from "./App";
import { api, type CreatureSummary, type ProfileView } from "./api";
import { Asset, Btn, CreatureCard, Empty, Panel, Stage } from "./ui";

const ACTIONS: { label: string; sub: string; accent: "purple" | "cyan" | "teal" | "gold"; route: Parameters<Go>[0] }[] = [
  { label: "CREATE CHIMERA", sub: "Build your own awesome chimera!", accent: "purple", route: { name: "lab" } },
  { label: "MY CODEX", sub: "Discover and learn about your chimeras!", accent: "cyan", route: { name: "codex" } },
  { label: "BATTLE BRACKET", sub: "Send eight into the arena!", accent: "teal", route: { name: "arena" } },
  { label: "HALL OF CHAMPIONS", sub: "See the champions and records!", accent: "gold", route: { name: "hall" } },
];

export function Home({ go, profile }: { go: Go; profile: ProfileView | null }) {
  const [featured, setFeatured] = useState<CreatureSummary | null>(null);
  const [crew, setCrew] = useState<CreatureSummary[]>([]);

  useEffect(() => {
    api
      .listCreatures("newest")
      .then((rows) => {
        setFeatured(rows[0] ?? null);
        setCrew(rows.slice(0, 4));
      })
      .catch(() => setCrew([]));
  }, []);

  const stats: [string, string, string][] = [
    ["total", "TOTAL CHIMERAS", String(profile?.total_creatures ?? 0)],
    ["wins", "BATTLES WON", String(profile?.battles_won ?? 0)],
    ["biggest", "BIGGEST CREATURE", profile?.biggest_creature?.name ?? "—"],
    ["champion", "CURRENT CHAMPION", profile?.current_champion?.name ?? "—"],
  ];

  return (
    <div className="home">
      <section className="home__hero">
        <div className="home__welcome">
          <p className="eyebrow">WELCOME BACK,</p>
          <h1 className="display display--xl">{(profile?.name ?? "BUILDER").toUpperCase()}!</h1>
          <div className="rule" />
          <p className="lede">
            Fuse four creatures into one amazing chimera, then send it into the arena
            to find out who really wins.
          </p>
          <Btn accent="purple" size="lg" onClick={() => go({ name: "lab" })}>
            START BUILDING
          </Btn>
        </div>

        <Stage creature={featured} caption="NO CHIMERAS YET" />

        <Panel title="QUICK STATS" accent="cyan" className="home__stats">
          {stats.map(([key, label, value]) => (
            <div className="qstat" key={key}>
              <Asset slot={`icons/quick_${key}`} label="" className="qstat__icon" />
              <div>
                <div className="qstat__label">{label}</div>
                <div className="qstat__value">{value}</div>
              </div>
            </div>
          ))}
        </Panel>
      </section>

      <section className="home__lower">
        <Panel title="TODAY'S CREW" accent="cyan" className="home__crew">
          {crew.length ? (
            <div className="home__crewgrid">
              {crew.map((c) => (
                <CreatureCard
                  key={c.id}
                  creature={c}
                  onClick={() => go({ name: "codex", id: c.id })}
                />
              ))}
            </div>
          ) : (
            <Empty title="No chimeras yet" hint="Head to the Fusion Lab and build your first one." />
          )}
        </Panel>

        <div className="home__actions">
          {ACTIONS.map((a) => (
            <button
              key={a.label}
              type="button"
              className={`tile tile--${a.accent}`}
              onClick={() => go(a.route)}
            >
              <Asset slot={`icons/tile_${a.label.split(" ")[0].toLowerCase()}`} label="" className="tile__icon" />
              <div className="tile__label">{a.label}</div>
              <div className="tile__sub">{a.sub}</div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
