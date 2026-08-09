/* Shared atoms for the neon-lab direction (docs/UI_STANDARD.md).
   Every painted asset goes through <Asset>, which falls back to a LOUD magenta
   gap marker — we want to see missing art, not hide it politely. Generated
   creature renders go through <MediaImg>, whose "not painted yet" state is a
   crafted holo-plate, because a creature without a render is not a missing
   asset slot. Never an emoji (ARCHITECTURE.md non-negotiable). */
import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CoreStats, CreatureSummary } from "./api";

/* One map from the slot names screens ask for to the files the art pipeline
   actually ships. Screens keep their readable names; new art only ever needs a
   line here. Anything unlisted resolves straight to /assets/<slot>.png. */
const SLOT_ALIASES: Record<string, string> = {
  "ui/logo": "ui/logo_mark",
  "ui/avatar": "avatar/henry_a",
  "ui/tbd": "ui/slot_empty",
  "ui/mascot": "lab/mascot",

  // Facts and abilities borrow the stat icons until purpose-made art lands.
  "icons/fact_strength": "icons/stat_power",
  "icons/ability": "icons/ability_generic",
  // No dedicated "a creature" glyph ships yet — the paw-on-leaf reads as one.
  "icons/creatures": "icons/cat_living",

  // Battle "why" icons map onto the five stats plus three of their own.
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
  "icons/quick_total": "icons/cat_living",
  "icons/quick_wins": "icons/nav_arena",
  "icons/quick_biggest": "icons/stat_size",
  "icons/quick_champion": "trophy/badge_champion",
  "icons/sort_all": "icons/tile_codex",
  "icons/sort_newest": "icons/tile_codex",
  "icons/sort_favorites": "icons/fact_fun",
  "icons/sort_winners": "icons/tile_hall",
  "icons/sort_biggest": "icons/stat_size",
  "icons/sort_fastest": "icons/stat_speed",
  "icons/sort_strongest": "icons/stat_power",
  "icons/record_biggest": "icons/stat_size",
  "icons/record_fastest": "icons/stat_speed",
  "icons/record_strongest": "icons/stat_power",
  "icons/record_most_wins": "trophy/badge_champion",
  "icons/record_champion": "trophy/badge_champion",
  "icons/record_toughest": "icons/stat_armor",
  "icons/record_special": "icons/stat_special",
  "icons/star": "icons/fact_fun",
  "icons/search": "icons/range",
  "icons/dice": "icons/stat_special",
};

/** The nine arenas, keyed to the small painted element icons. */
export const ENV_ICON: Record<string, string> = {
  city_harbor: "icons/env_crane",
  deep_ocean: "icons/env_depth",
  desert_ruins: "icons/env_ruins",
  frozen_ridge: "icons/env_snow",
  jungle_canyon: "icons/env_leaf",
  open_sky: "icons/env_cloud",
  storm_coast: "icons/env_lightning",
  swamp: "icons/env_mud",
  volcanic_shore: "icons/env_fire",
};

export function envIcon(slug: string): string {
  return ENV_ICON[slug] ?? "icons/env_leaf";
}

/** The eight reason keys the battle service templates ship. gpt-5.1 writes its
    own titles and may hand back a key we never painted — anything unknown
    resolves to the generic ability glyph rather than a magenta gap. */
const REASON_KEYS = new Set([
  "armor", "speed", "power", "size", "special",
  "environment", "endurance", "range", "mobility",
]);

export function reasonIcon(icon: string, environment: string): string {
  const key = (icon || "").toLowerCase();
  if (key === "environment") return envIcon(environment);
  if (REASON_KEYS.has(key)) return `icons/reason_${key}`;
  if (ENV_ICON[key]) return ENV_ICON[key];
  return "icons/ability_generic";
}

export function envLabel(slug: string): string {
  return slug.replace(/[_-]/g, " ").toUpperCase();
}

function resolveSlot(slot: string): string {
  return SLOT_ALIASES[slot] ?? slot;
}

/** Loads /assets/<slot>.png; a miss renders the magenta gap marker. */
export function Asset({
  slot,
  label,
  className = "",
  tint,
}: {
  slot: string;
  label?: string;
  className?: string;
  /** Painted icons ship cyan; tint recolours them to a screen's accent. */
  tint?: "purple" | "gold" | "teal" | "green" | "red";
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [slot]);

  const file = resolveSlot(slot);
  const cls = `asset${tint ? ` tint-${tint}` : ""} ${className}`;
  if (failed) {
    const decorative = label === "";
    return (
      <div
        className={`${cls} asset--fallback${decorative ? " asset--quiet" : ""}`}
        aria-label={decorative ? undefined : label || slot}
        aria-hidden={decorative || undefined}
      >
        <span className="asset__slot">{label || slot}</span>
      </div>
    );
  }
  return (
    <img
      className={cls}
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
  note = "RENDER PENDING",
}: {
  src: string | null | undefined;
  alt: string;
  className?: string;
  note?: string;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  if (!src || failed) {
    return (
      <div className={`pending ${className}`} aria-label={alt}>
        <img className="pending__mark" src="/assets/ui/logo_mark.png" alt="" aria-hidden="true" />
        <span className="pending__label">{note}</span>
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
  note,
}: {
  creature: Pick<CreatureSummary, "name" | "hero_image_path" | "thumb_path"> | null | undefined;
  prefer?: "thumb" | "hero";
  className?: string;
  note?: string;
}) {
  const src =
    prefer === "hero"
      ? creature?.hero_image_path || creature?.thumb_path
      : creature?.thumb_path || creature?.hero_image_path;
  return (
    <MediaImg src={src} alt={creature?.name || "chimera"} className={className} note={note} />
  );
}

/** True when a creature has a render we can put on a platform. */
export function hasArt(c: Pick<CreatureSummary, "hero_image_path" | "thumb_path"> | null | undefined) {
  return Boolean(c && (c.hero_image_path || c.thumb_path));
}

/** A name plate that never breaks a word. Long names shrink until the text
    fits its box (width and any line-clamped height) instead of hyphenless
    mid-word breaks or ellipsis; wrapping at word boundaries stays allowed.
    Every creature-name plate, label and chip renders through this. */
export function FitText({
  children,
  className = "",
  min = 8,
}: {
  children: React.ReactNode;
  className?: string;
  /** Smallest font-size in px before the CSS backstop takes over. */
  min?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);

  const fit = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    // Inline boxes report clientWidth 0 — measurement needs a block box.
    if (window.getComputedStyle(el).display === "inline") el.style.display = "block";
    el.style.fontSize = "";
    const base = parseFloat(window.getComputedStyle(el).fontSize) || 0;
    if (!base) return;
    const overflows = () =>
      el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1;
    let size = base;
    while (size > min && overflows()) {
      size = Math.max(min, size - 0.5);
      el.style.fontSize = `${size}px`;
    }
  }, [min]);

  useLayoutEffect(fit); // after every render — the text may have changed

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(fit); // the box may have changed
    ro.observe(el.parentElement ?? el);
    return () => ro.disconnect();
  }, [fit]);

  return (
    <span ref={ref} className={className}>
      {children}
    </span>
  );
}

export type Accent = "cyan" | "purple" | "gold" | "teal";

export function Panel({
  title,
  icon,
  accent = "cyan",
  className = "",
  action,
  children,
}: {
  title?: string;
  icon?: string;
  accent?: Accent;
  className?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className={`panel panel--${accent} ${className}`}>
      {title && (
        <header className="panel__head">
          <h2>
            {icon && <Asset slot={icon} label="" className="panel__icon" tint={tintFor(accent)} />}
            {title}
          </h2>
          {action}
        </header>
      )}
      <div className="panel__body">{children}</div>
    </section>
  );
}

function tintFor(accent: Accent): "purple" | "gold" | "teal" | undefined {
  return accent === "cyan" ? undefined : accent;
}

export function Btn({
  children,
  onClick,
  accent = "cyan",
  size = "md",
  disabled,
  sub,
  active,
  icon,
  className = "",
  title,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  accent?: Accent | "ghost" | "green";
  size?: "sm" | "md" | "lg" | "xl";
  disabled?: boolean;
  sub?: string;
  active?: boolean;
  icon?: string;
  className?: string;
  title?: string;
}) {
  return (
    <button
      type="button"
      className={`btn btn--${accent} btn--${size}${active ? " is-active" : ""} ${className}`}
      onClick={onClick}
      disabled={disabled}
      title={title}
    >
      <span className="btn__row">
        {icon && (
          <Asset
            slot={icon}
            label=""
            className="btn__icon"
            tint={accent === "purple" || accent === "gold" || accent === "teal" ? accent : undefined}
          />
        )}
        <span className="btn__label">{children}</span>
      </span>
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

/** Three stacked segments, as the reveal mock paints its stat bars. */
export function Bars({ value, tone = "cyan", segments = 3 }: { value: number; tone?: string; segments?: number }) {
  const step = 100 / segments;
  return (
    <div className="bars" data-tone={tone}>
      {Array.from({ length: segments }).map((_, i) => {
        const fill = Math.max(0, Math.min(1, (value - i * step) / step));
        return (
          <i key={i}>
            <b style={{ width: `${fill * 100}%` }} />
          </i>
        );
      })}
    </div>
  );
}

export const STAT_TONES: Record<string, string> = {
  power: "purple",
  speed: "cyan",
  armor: "green",
  size: "gold",
  special: "orange",
};

const STAT_TINT: Record<string, "purple" | "gold" | "teal" | "green" | "red" | undefined> = {
  power: "purple",
  speed: undefined,
  armor: "green",
  size: "gold",
  special: "red",
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
          <span className={`stat__ring t-${STAT_TONES[key] === "orange" ? "red" : STAT_TONES[key]}`}>
            <Asset slot={`icons/stat_${key}`} label="" className="stat__icon" tint={STAT_TINT[key]} />
          </span>
          <FitText className="stat__name">
            {key === "special" ? stats.special_name || "Special" : key}
          </FitText>
          <Bars value={value} tone={STAT_TONES[key]} />
          <div className="stat__value num">{value}</div>
        </div>
      ))}
    </div>
  );
}

/** The holo platform a creature always stands on — the anchor of every screen. */
export function Stage({
  creature,
  caption,
  fusing,
  gold,
  flip,
  children,
  className = "",
}: {
  creature?: CreatureSummary | null;
  caption?: string;
  fusing?: boolean;
  gold?: boolean;
  /** Mirror the render so two fighters face each other across the arena. */
  flip?: boolean;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`stage${fusing ? " stage--fusing" : ""}${gold ? " stage--gold" : ""} ${className}`}
    >
      <div className="stage__glow" />
      <div className="stage__platform">
        <Asset slot={gold ? "lab/platform_gold" : "lab/platform"} label="" />
      </div>
      <div className="stage__contact" />
      <div className={`stage__subject${flip ? " is-flipped" : ""}`}>
        {children ??
          (creature ? (
            <CreatureImg creature={creature} prefer="hero" note={caption || "RENDER PENDING"} />
          ) : (
            <div className="pending">
              <img className="pending__mark" src="/assets/ui/logo_mark.png" alt="" aria-hidden="true" />
              <span className="pending__label">{caption || "AWAITING FUSION"}</span>
            </div>
          ))}
      </div>
    </div>
  );
}

export function RarityBadge({ rarity }: { rarity: string }) {
  if (!rarity) return null; // a failed splice has no rarity — no empty pill
  const tone =
    rarity === "Legendary" ? "gold" : rarity === "Epic" ? "purple" : rarity === "Rare" ? "cyan" : "muted";
  return <Badge tone={tone as "gold"}>{rarity}</Badge>;
}

export function CreatureCard({
  creature,
  selected,
  onClick,
  corner,
  showTrophies = true,
}: {
  creature: CreatureSummary;
  selected?: boolean;
  onClick?: () => void;
  corner?: React.ReactNode;
  showTrophies?: boolean;
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
      <div className="ccard__plate">
        <FitText className="ccard__name">{creature.name || "UNNAMED SPLICE"}</FitText>
        <div className="ccard__meta">
          <RarityBadge rarity={creature.rarity} />
          {showTrophies && (
            <span className="ccard__trophy num">
              <Asset slot="trophy/badge_champion" label="" />
              {creature.wins}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="empty">
      <Asset slot="ui/mascot" label="" className="empty__mascot" />
      <div className="empty__title">{title}</div>
      {hint && <div className="empty__hint">{hint}</div>}
    </div>
  );
}

export function Loading({ label = "LOADING" }: { label?: string }) {
  return (
    <div className="loading">
      <div className="loading__ring" />
      <span>{label}</span>
    </div>
  );
}
