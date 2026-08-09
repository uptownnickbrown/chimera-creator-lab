/* Typed client for the Chimera Creator API. No state library, no auth yet —
   single player, one origin. Types mirror backend/app/schemas.py. */

const BASE = import.meta.env.VITE_API_URL || "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}/api${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : null) as T;
}

// -- shapes -------------------------------------------------------------------

export type ImageStatus = "pending" | "complete" | "failed";
export type RecordStatus = "generating" | "complete" | "failed";
export type Rarity = "Uncommon" | "Rare" | "Epic" | "Legendary";
export type CodexSort =
  | "newest" | "biggest" | "fastest" | "strongest" | "winners" | "favorites";

export interface CoreStats {
  power: number;
  speed: number;
  armor: number;
  size: number;
  special_name: string;
  special: number;
}

export interface Ability {
  name: string;
  blurb: string;
  sources: string[];
}

export interface CreatureSummary {
  id: number;
  name: string;
  title: string;
  rarity: Rarity | string;
  role: string;
  sources: string[];
  core_stats: Partial<CoreStats>;
  /** "generating" while the gpt-5.1 record streams; fields below fill in live. */
  record_status: RecordStatus;
  image_status: ImageStatus;
  /** Streaming preview: ability names revealed so far. Empty once complete. */
  ability_names: string[];
  hero_image_path: string | null;
  thumb_path: string | null;
  favorite: boolean;
  wins: number;
  losses: number;
  championships: number;
  created_at: string | null;
}

export interface CreatureDetail extends CreatureSummary {
  abilities: Ability[];
  strengths: string[];
  weaknesses: string[];
  environment_affinities: Record<string, number>;
  fun_fact: string;
  anatomy_plan: string;
  visual_spec: string;
  records: Record<string, string>;
  win_rate: number;
}

export interface SourceCreature {
  slug: string;
  name: string;
  category: string;
  contribution: string;
  blurb: string;
  /** The authored `contributes` list — what this part adds, child-facing. */
  traits: string[];
  tags: string[];
  art: string | null;
  /** Authored misspellings and nicknames ("draggon", "wyvern"). Optional:
      the field is in data/source_creatures.json and the picker searches it as
      soon as /api/library starts serving it. */
  aliases?: string[];
  /** True for parts Henry summoned himself (backend custom_parts table).
      Custom parts carry their portrait in `art` (a /media path) — it is null
      while the portrait is still being painted. */
  custom?: boolean;
}

export interface SummonResponse {
  status: "matched" | "disambiguate" | "conjured" | "redirect";
  source: SourceCreature | null;
  candidates: SourceCreature[];
  message: string;
  /** conjured only: "rendering" | "complete" | "failed" */
  portrait_status: string;
}

export interface Environment {
  slug: string;
  name: string;
  blurb: string;
  art: string | null;
}

export interface LibraryResponse {
  sources: SourceCreature[];
  environments: Environment[];
  loaded: boolean;
}

export interface BracketMatch {
  id: string;
  a: number | null;
  b: number | null;
  winner: number | null;
  battle_id: number | null;
  environment: string;
  predicted: number | null;
  prediction_correct: boolean | null;
}

export interface BracketRound {
  name: string;
  matches: BracketMatch[];
}

export interface TournamentView {
  id: number;
  name: string;
  status: "setup" | "active" | "complete";
  entrant_ids: number[];
  rounds: BracketRound[];
  champion_id: number | null;
  entrants: CreatureSummary[];
  created_at: string | null;
  completed_at: string | null;
  /** Championship key art: "pending" while it renders, then a /media path.
      Optional — the ceremony composites its own finale when it is absent. */
  final_art?: string | null;
}

export interface BattleReason {
  icon: string;
  title: string;
  blurb: string;
}

export interface BattleView {
  battle_id: number;
  match_id: string;
  creature_a_id: number;
  creature_b_id: number;
  environment: string;
  winner_id: number;
  confidence: number;
  reasons: BattleReason[];
  narrative: string;
  beats: string[];
  health_remaining: { a: number; b: number };
  predicted: number | null;
  prediction_correct: boolean | null;
  cached: boolean;
}

export interface ResolveResponse {
  battle: BattleView;
  tournament: TournamentView;
}

export interface ProfileView {
  name: string;
  avatar: string;
  level: number;
  xp: number;
  xp_to_next: number;
  settings: Record<string, unknown>;
  total_creatures: number;
  battles_won: number;
  biggest_creature: CreatureSummary | null;
  current_champion: CreatureSummary | null;
  favorites: CreatureSummary[];
}

export interface HallRecord {
  key: string;
  label: string;
  value: string;
  creature: CreatureSummary | null;
}

export interface HallView {
  champions: CreatureSummary[];
  top_winners: CreatureSummary[];
  records: HallRecord[];
}

// -- endpoints ----------------------------------------------------------------

export const api = {
  createCreature: (source_slugs: string[]) =>
    request<{ creature_id: number; status: ImageStatus }>("POST", "/creatures", {
      source_slugs,
    }),
  getCreature: (id: number) => request<CreatureDetail>("GET", `/creatures/${id}`),
  retryImage: (id: number) =>
    request<{ creature_id: number; status: ImageStatus }>(
      "POST",
      `/creatures/${id}/retry-image`,
    ),
  listCreatures: (sort: CodexSort = "newest") =>
    request<CreatureSummary[]>("GET", `/creatures?sort=${sort}`),
  toggleFavorite: (id: number) =>
    request<{ creature_id: number; favorite: boolean }>("POST", `/creatures/${id}/favorite`),
  rerollName: (id: number) =>
    request<{ creature_id: number; name: string; title: string }>(
      "POST",
      `/creatures/${id}/rename`,
    ),

  getLibrary: () => request<LibraryResponse>("GET", "/library"),
  summon: (query: string) => request<SummonResponse>("POST", "/library/summon", { query }),

  listTournaments: () => request<TournamentView[]>("GET", "/tournaments"),
  createTournament: (entrant_ids: number[], name?: string) =>
    request<TournamentView>("POST", "/tournaments", { entrant_ids, name }),
  getTournament: (id: number) => request<TournamentView>("GET", `/tournaments/${id}`),
  predict: (tournamentId: number, matchId: string, pick_id: number) =>
    request<TournamentView>(
      "POST",
      `/tournaments/${tournamentId}/matches/${matchId}/predict`,
      { pick_id },
    ),
  resolve: (tournamentId: number, matchId: string) =>
    request<ResolveResponse>(
      "POST",
      `/tournaments/${tournamentId}/matches/${matchId}/resolve`,
    ),

  getProfile: () => request<ProfileView>("GET", "/profile"),
  getHall: () => request<HallView>("GET", "/hall"),
};

/** The gene library never changes inside a session — fetch it once, share it.
    The Fusion Wait needs it mid-flight and must not pay for a round trip. */
let libraryPromise: Promise<LibraryResponse> | null = null;
export function getLibraryCached(): Promise<LibraryResponse> {
  if (!libraryPromise) {
    libraryPromise = api.getLibrary().catch((err) => {
      libraryPromise = null; // a failed fetch must not poison the cache
      throw err;
    });
  }
  return libraryPromise;
}

/** Summoning changes the library (a new part, then its portrait landing) —
    drop the session cache and refetch so every later consumer sees it. */
export function refreshLibrary(): Promise<LibraryResponse> {
  libraryPromise = null;
  return getLibraryCached();
}
