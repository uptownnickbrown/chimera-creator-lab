/* Screen 1 — Home / Welcome (spec §17, art-direction/welcome.png).
   The featured chimera stands large on the platform in the middle of the lab;
   everything else frames it and nothing covers it. */
import { useEffect, useState } from "react";
import type { Go } from "./App";
import { api, type CreatureSummary, type ProfileView } from "./api";
import { Asset, Btn, CreatureImg, Empty, FitText, Panel, RarityBadge, Stage, hasArt } from "./ui";

const ACTIONS: {
  label: string;
  lines: [string, string];
  sub: string;
  accent: "purple" | "cyan" | "teal" | "gold";
  icon: string;
  route: Parameters<Go>[0];
}[] = [
  {
    label: "CREATE CHIMERA",
    lines: ["CREATE", "CHIMERA"],
    sub: "Build your own awesome chimera!",
    accent: "purple",
    icon: "icons/tile_create",
    route: { name: "lab" },
  },
  {
    label: "MY CODEX",
    lines: ["MY", "CODEX"],
    sub: "Discover and learn about your chimeras!",
    accent: "cyan",
    icon: "icons/tile_my",
    route: { name: "codex" },
  },
  {
    label: "BATTLE BRACKET",
    lines: ["BATTLE", "BRACKET"],
    sub: "Send eight into the arena and climb!",
    accent: "teal",
    icon: "icons/tile_battle",
    route: { name: "arena" },
  },
  {
    label: "HALL OF CHAMPIONS",
    lines: ["HALL OF", "CHAMPIONS"],
    sub: "See the top champions and records!",
    accent: "gold",
    icon: "icons/tile_hall",
    route: { name: "hall" },
  },
];

export function Home({ go, profile }: { go: Go; profile: ProfileView | null }) {
  const [rows, setRows] = useState<CreatureSummary[] | null>(null);

  useEffect(() => {
    api
      .listCreatures("newest")
      .then(setRows)
      .catch(() => setRows([]));
  }, []);

  const painted = (rows ?? []).filter(hasArt);
  /* The champion earns the platform; otherwise the newest painted chimera. */
  const champ = profile?.current_champion;
  const featured =
    (champ && painted.find((c) => c.id === champ.id)) ?? painted[0] ?? rows?.[0] ?? null;
  const crew = (painted.length ? painted : rows ?? []).slice(0, 4);

  /* `tint` is explicit, not derived from the tone: badge_champion already
     ships gold and must not be hue-rotated a second time. */
  const stats: {
    key: string;
    label: string;
    value: string;
    tone: "cyan" | "purple" | "teal" | "gold";
    tint?: "purple" | "teal" | "gold";
    foot?: string;
  }[] = [
    {
      key: "total",
      label: "TOTAL CHIMERAS",
      value: String(profile?.total_creatures ?? 0),
      tone: "cyan",
    },
    {
      key: "wins",
      label: "BATTLES WON",
      value: String(profile?.battles_won ?? 0),
      tone: "purple",
      tint: "purple",
    },
    {
      key: "biggest",
      label: "BIGGEST CREATURE",
      value: profile?.biggest_creature?.name || "NOT YET",
      tone: "teal",
      tint: "teal",
      foot: profile?.biggest_creature ? `SIZE ${profile.biggest_creature.core_stats.size ?? "—"}` : undefined,
    },
    {
      key: "champion",
      label: "CURRENT CHAMPION",
      value: profile?.current_champion?.name || "UNCROWNED",
      tone: "gold",
      foot: profile?.current_champion
        ? `${profile.current_champion.championships} TITLE${profile.current_champion.championships === 1 ? "" : "S"}`
        : undefined,
    },
  ];

  return (
    <div className="home screen-in">
      <section className="home__welcome">
        <p className="eyebrow">WELCOME BACK,</p>
        <h1 className="display display--xl">{(profile?.name ?? "BUILDER").toUpperCase()}!</h1>
        <div className="rule" />
        <p className="lede">
          Fuse four creatures into one amazing chimera, then send it into the arena
          to find out who really wins!
        </p>
        <Btn accent="purple" size="xl" className="home__cta" onClick={() => go({ name: "lab" })}>
          START BUILDING
        </Btn>
      </section>

      <section className="home__stage">
        <Stage creature={featured} caption="NO CHIMERAS YET" />
        {featured && (
          <div className="home__nameplate">
            <span className="home__featname">{(featured.name || "UNNAMED SPLICE").toUpperCase()}</span>
            <span className="home__featmeta">
              <RarityBadge rarity={featured.rarity} />
              <span className="muted">{featured.title || featured.role}</span>
            </span>
          </div>
        )}
      </section>

      <Panel title="QUICK STATS" accent="cyan" className="home__stats">
        <div className="cascade qstats">
          {stats.map((s) => (
            <div className={`qstat t-${s.tone}`} key={s.key}>
              <span className="qstat__ring">
                <Asset slot={`icons/quick_${s.key}`} label="" className="qstat__icon" tint={s.tint} />
              </span>
              <div className="qstat__text">
                <div className="qstat__label">{s.label}</div>
                <FitText className="qstat__value num">{s.value.toUpperCase()}</FitText>
                {s.foot && <div className="qstat__foot num">{s.foot}</div>}
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="TODAY'S CREW" accent="cyan" className="home__crew">
        {crew.length ? (
          <div className="crewrow">
            {crew.map((c) => (
              <button
                type="button"
                className="crew"
                key={c.id}
                onClick={() => go({ name: "codex", id: c.id })}
              >
                <span className="crew__art">
                  <CreatureImg creature={c} />
                  {c.favorite && <span className="ccard__fav" />}
                </span>
                <FitText className="crew__name">{(c.name || "UNNAMED").toUpperCase()}</FitText>
                <span className="crew__meta num">
                  {c.wins}W · {c.losses}L
                </span>
              </button>
            ))}
          </div>
        ) : (
          <Empty title="No chimeras yet" hint="Head to the Fusion Lab and build your first one." />
        )}
      </Panel>

      <nav className="home__actions">
        {ACTIONS.map((a) => (
          <button
            key={a.label}
            type="button"
            className={`tile tile--${a.accent}`}
            onClick={() => go(a.route)}
            aria-label={a.label}
          >
            <span className="tile__glow" />
            <Asset
              slot={a.icon}
              label=""
              className="tile__icon"
              tint={a.accent === "cyan" ? undefined : a.accent}
            />
            <span className="tile__label">
              {a.lines[0]}
              <br />
              {a.lines[1]}
            </span>
            <span className="tile__sub">{a.sub}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
