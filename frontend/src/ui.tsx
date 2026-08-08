/* Shared atoms for the neon-lab direction. Every painted asset goes through
   <Asset>, which falls back to a styled slot plate — never an emoji
   (ARCHITECTURE.md non-negotiable). */
import React, { useEffect, useState } from "react";
import type { CoreStats, CreatureSummary } from "./api";

function hue(slot: string): number {
  let h = 0;
  for (let i = 0; i < slot.length; i++) h = (h * 31 + slot.charCodeAt(i)) % 360;
  return 190 + ((h % 110) - 20); // stay inside the cyan -> violet band
}

/** Loads /assets/<slot>.png; degrades to a labelled plate until the art lands. */
export function Asset({
  slot,
  label,
  className = "",
}: {
  slot: string;
  label?: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [slot]);

  const style = { "--asset-hue": hue(slot) } as React.CSSProperties;
  if (failed) {
    return (
      <div className={`asset asset--fallback ${className}`} style={style} aria-label={label || slot}>
        <span className="asset__slot">{label || slot}</span>
      </div>
    );
  }
  return (
    <img
      className={`asset ${className}`}
      style={style}
      src={`/assets/${slot}.png`}
      alt={label || slot}
      onError={() => setFailed(true)}
    />
  );
}

export function Panel({
  title,
  accent = "cyan",
  className = "",
  action,
  children,
}: {
  title?: string;
  accent?: "cyan" | "purple" | "gold" | "teal";
  className?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className={`panel panel--${accent} ${className}`}>
      {title && (
        <header className="panel__head">
          <h2>{title}</h2>
          {action}
        </header>
      )}
      <div className="panel__body">{children}</div>
    </section>
  );
}

export function Btn({
  children,
  onClick,
  accent = "cyan",
  size = "md",
  disabled,
  sub,
  active,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  accent?: "cyan" | "purple" | "gold" | "teal" | "ghost";
  size?: "md" | "lg";
  disabled?: boolean;
  sub?: string;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      className={`btn btn--${accent} btn--${size}${active ? " is-active" : ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      <span className="btn__label">{children}</span>
      {sub && <span className="btn__sub">{sub}</span>}
    </button>
  );
}

export function Badge({
  children,
  tone = "purple",
}: {
  children: React.ReactNode;
  tone?: "purple" | "cyan" | "gold" | "green" | "red" | "muted";
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function Meter({
  value,
  max = 100,
  tone = "cyan",
}: {
  value: number;
  max?: number;
  tone?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="meter" data-tone={tone}>
      <div className="meter__fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

const STAT_TONES: Record<string, string> = {
  power: "purple",
  speed: "cyan",
  armor: "green",
  size: "gold",
  special: "orange",
};

/** The five child-facing stats (spec §12), tabular numerals, 0-100. */
export function StatRow({ stats }: { stats: Partial<CoreStats> }) {
  const entries: [string, number][] = [
    ["power", stats.power ?? 0],
    ["speed", stats.speed ?? 0],
    ["armor", stats.armor ?? 0],
    ["size", stats.size ?? 0],
    ["special", stats.special ?? 0],
  ];
  return (
    <div className="statrow">
      {entries.map(([key, value]) => (
        <div className="stat" key={key}>
          <Asset slot={`icons/stat_${key}`} label={key} className="stat__icon" />
          <div className="stat__name">
            {key === "special" ? stats.special_name || "Special" : key}
          </div>
          <Meter value={value} tone={STAT_TONES[key]} />
          <div className="stat__value num">{value}</div>
        </div>
      ))}
    </div>
  );
}

/** The holo platform the creature stands on — the visual anchor of every screen. */
export function Stage({
  creature,
  caption,
  fusing,
}: {
  creature?: CreatureSummary | null;
  caption?: string;
  fusing?: boolean;
}) {
  return (
    <div className={`stage${fusing ? " stage--fusing" : ""}`}>
      <div className="stage__glow" />
      <div className="stage__subject">
        {creature ? (
          <Asset
            slot={creature.hero_image_path ? `creatures/${creature.id}` : `creatures/${creature.id}`}
            label={creature.name}
            className="stage__hero"
          />
        ) : (
          <div className="stage__empty">{caption || "AWAITING FUSION"}</div>
        )}
      </div>
      <div className="stage__platform">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

export function RarityBadge({ rarity }: { rarity: string }) {
  const tone =
    rarity === "Legendary" ? "gold" : rarity === "Epic" ? "purple" : rarity === "Rare" ? "cyan" : "muted";
  return <Badge tone={tone as "gold"}>{rarity}</Badge>;
}

export function CreatureCard({
  creature,
  selected,
  onClick,
  corner,
}: {
  creature: CreatureSummary;
  selected?: boolean;
  onClick?: () => void;
  corner?: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className={`ccard${selected ? " is-selected" : ""}`}
      onClick={onClick}
      disabled={!onClick}
    >
      <div className="ccard__art">
        <Asset slot={`creatures/${creature.id}`} label={creature.name} />
        {creature.favorite && <span className="ccard__fav" aria-label="favorite" />}
        {corner && <span className="ccard__corner">{corner}</span>}
      </div>
      <div className="ccard__name">{creature.name}</div>
      <div className="ccard__meta">
        <RarityBadge rarity={creature.rarity} />
        <span className="num">{creature.wins}W</span>
        <span className="num muted">{creature.losses}L</span>
      </div>
    </button>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="empty">
      <div className="empty__title">{title}</div>
      {hint && <div className="empty__hint">{hint}</div>}
    </div>
  );
}

export function Loading({ label = "LOADING" }: { label?: string }) {
  return (
    <div className="loading">
      <div className="loading__bar" />
      <span>{label}</span>
    </div>
  );
}
