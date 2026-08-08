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

/* One map from the slot names screens ask for to the files the art pipeline
   actually ships. Screens keep their readable names; new art only ever needs a
   line here. Anything unlisted resolves straight to /assets/<slot>.png. */
const SLOT_ALIASES: Record<string, string> = {
  "ui/logo": "ui/logo_mark",
  "ui/avatar": "avatar/henry_a",
  "ui/tbd": "ui/slot_empty",

  // Facts and abilities borrow the stat icons until purpose-made art lands.
  "icons/fact_strength": "icons/stat_power",
  "icons/ability": "icons/stat_special",

  // Battle "why" icons map onto the five stats plus two of their own.
  "icons/reason_armor": "icons/stat_armor",
  "icons/reason_speed": "icons/stat_speed",
  "icons/reason_power": "icons/stat_power",
  "icons/reason_size": "icons/stat_size",
  "icons/reason_special": "icons/stat_special",
  "icons/reason_mobility": "icons/stat_speed",
  "icons/reason_endurance": "icons/endurance",
  "icons/reason_range": "icons/range",
  "icons/reason_environment": "icons/env_leaf",

  // Home tiles / quick stats / codex sorts / hall records.
  "icons/tile_create": "icons/tile_create",
  "icons/tile_my": "icons/tile_codex",
  "icons/tile_battle": "icons/tile_arena",
  "icons/tile_hall": "icons/tile_hall",
  "icons/quick_total": "icons/creatures",
  "icons/quick_wins": "icons/stat_power",
  "icons/quick_biggest": "icons/stat_size",
  "icons/quick_champion": "trophy/badge_champion",
  "icons/sort_newest": "icons/creatures",
  "icons/sort_favorites": "icons/stat_special",
  "icons/sort_winners": "trophy/badge_champion",
  "icons/sort_biggest": "icons/stat_size",
  "icons/sort_fastest": "icons/stat_speed",
  "icons/sort_strongest": "icons/stat_power",
  "icons/record_biggest": "icons/stat_size",
  "icons/record_fastest": "icons/stat_speed",
  "icons/record_strongest": "icons/stat_power",
  "icons/record_most_wins": "trophy/badge_champion",
  "icons/record_champion": "trophy/badge_champion",
};

function resolveSlot(slot: string): string {
  return SLOT_ALIASES[slot] ?? slot;
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

  const file = resolveSlot(slot);
  const style = { "--asset-hue": hue(slot) } as React.CSSProperties;
  if (failed) {
    // label="" marks a decorative icon: the plate stays quiet rather than
    // shouting a slot path at a seven-year-old. Named assets keep their label.
    const decorative = label === "";
    return (
      <div
        className={`asset asset--fallback${decorative ? " asset--quiet" : ""} ${className}`}
        style={style}
        aria-hidden={decorative || undefined}
        aria-label={decorative ? undefined : label || slot}
      >
        {!decorative && <span className="asset__slot">{label || slot}</span>}
      </div>
    );
  }
  return (
    <img
      className={`asset ${className}`}
      style={style}
      src={`/assets/${file}.png`}
      alt={label || slot}
      onError={() => setFailed(true)}
    />
  );
}

/** Generated creature art lives on /media (backend-owned), never in /assets —
    always render hero_image_path / thumb_path, never an invented slot name. */
export function MediaImg({
  src,
  alt,
  className = "",
}: {
  src: string | null | undefined;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  if (!src || failed) {
    return (
      <div className={`asset asset--fallback ${className}`} aria-label={alt}>
        <span className="asset__slot">{alt}</span>
      </div>
    );
  }
  return (
    <img className={`asset ${className}`} src={src} alt={alt} onError={() => setFailed(true)} />
  );
}

/** A saved creature's art: thumbnail where one exists, hero otherwise. */
export function CreatureImg({
  creature,
  prefer = "thumb",
  className = "",
}: {
  creature: Pick<CreatureSummary, "name" | "hero_image_path" | "thumb_path"> | null | undefined;
  prefer?: "thumb" | "hero";
  className?: string;
}) {
  const src =
    prefer === "hero"
      ? creature?.hero_image_path || creature?.thumb_path
      : creature?.thumb_path || creature?.hero_image_path;
  return <MediaImg src={src} alt={creature?.name || "chimera"} className={className} />;
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
        {creature && (creature.hero_image_path || creature.thumb_path) ? (
          <CreatureImg creature={creature} prefer="hero" className="stage__hero" />
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
        <CreatureImg creature={creature} />
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
