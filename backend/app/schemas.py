"""Pydantic v2 contracts.

`CreatureRecord` is a faithful port of the JSON schema validated in the model
bakeoff (research/bakeoff/text_probe.py SCHEMA) — it is what gpt-5.1 returns
under structured output, and what the stub generator imitates. Keep the two in
sync: if a field changes here it must change in the prompt schema too.

`BattleResult` is the gpt-5.1 battle contract (spec §20, ARCHITECTURE.md).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Rarity = Literal["Uncommon", "Rare", "Epic", "Legendary"]

#: The nine arenas. Mirrors the environment_affinities keys in the probe schema.
ENVIRONMENT_SLUGS: tuple[str, ...] = (
    "deep_ocean",
    "storm_coast",
    "volcanic_shore",
    "jungle_canyon",
    "frozen_ridge",
    "open_sky",
    "desert_ruins",
    "swamp",
    "city_harbor",
)


class Strict(BaseModel):
    """additionalProperties: false, the pydantic way."""

    model_config = ConfigDict(extra="forbid")


# -- creature record (LLM contract) -------------------------------------------

class CoreStats(Strict):
    """Child-facing stats, 0-100. The fifth stat is creature-specific (§12)."""

    power: int = Field(ge=0, le=100)
    speed: int = Field(ge=0, le=100)
    armor: int = Field(ge=0, le=100)
    size: int = Field(ge=0, le=100)
    special_name: str = Field(description="One-word 5th stat name, e.g. Venom, Flight, Stealth")
    special: int = Field(ge=0, le=100)


class Ability(Strict):
    name: str
    blurb: str = Field(description="One short exciting sentence a 7-year-old can read")
    sources: list[str] = Field(
        description="Which source creatures combine into this ability — best abilities fuse two"
    )


class EnvironmentAffinities(Strict):
    """Score -2 (terrible) to +2 (dominant) per environment."""

    deep_ocean: int = Field(ge=-2, le=2)
    storm_coast: int = Field(ge=-2, le=2)
    volcanic_shore: int = Field(ge=-2, le=2)
    jungle_canyon: int = Field(ge=-2, le=2)
    frozen_ridge: int = Field(ge=-2, le=2)
    open_sky: int = Field(ge=-2, le=2)
    desert_ruins: int = Field(ge=-2, le=2)
    swamp: int = Field(ge=-2, le=2)
    city_harbor: int = Field(ge=-2, le=2)


class SimProfile(Strict):
    """Hidden simulation stats 0-100 — never rendered in the child-facing UI."""

    land_speed: int = Field(ge=0, le=100)
    swim_speed: int = Field(ge=0, le=100)
    flight_speed: int = Field(ge=0, le=100)
    bite_force: int = Field(ge=0, le=100)
    armor_rating: int = Field(ge=0, le=100)
    intelligence: int = Field(ge=0, le=100)
    endurance: int = Field(ge=0, le=100)
    regeneration: int = Field(ge=0, le=100)
    attack_range: int = Field(ge=0, le=100)
    maneuverability: int = Field(ge=0, le=100)


class CreatureRecord(Strict):
    """One coherent species fused from four sources."""

    name: str = Field(description="Exciting 1-3 word species name a 7-year-old can pronounce")
    title: str = Field(description="Epic short title like 'The Thundered Leviathan'")
    anatomy_plan: str = Field(description="How the four sources map to body systems")
    role: str = Field(description="Combat archetype, e.g. 'Bruiser / Area Control'")
    core_stats: CoreStats
    abilities: list[Ability] = Field(min_length=3, max_length=4)
    strengths: list[str] = Field(min_length=2, max_length=3)
    weaknesses: list[str] = Field(min_length=2, max_length=3)
    environment_affinities: EnvironmentAffinities
    sim_profile: SimProfile
    visual_spec: str = Field(description="Image-gen description: colors, textures, body plan")
    rarity: Rarity
    fun_fact: str


# -- battle contract (LLM) ----------------------------------------------------

class BattleReason(Strict):
    """One of exactly three child-facing reasons (spec §7 EXPLAIN)."""

    icon: str = Field(
        description="Icon slot keyword, never an emoji — e.g. 'armor', 'speed', 'environment'"
    )
    title: str
    blurb: str


class HealthRemaining(Strict):
    a: int = Field(ge=0, le=1000)
    b: int = Field(ge=0, le=1000)


class BattleResult(Strict):
    winner_slug_or_id: str = Field(description="id (or slug) of the winning creature")
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[BattleReason] = Field(min_length=3, max_length=3)
    narrative: str
    beats: list[str] = Field(min_length=4, max_length=6)
    health_remaining: HealthRemaining


# -- API response models ------------------------------------------------------

class Api(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CreateCreatureRequest(Api):
    source_slugs: list[str] = Field(min_length=4, max_length=4)


class CreateCreatureResponse(Api):
    creature_id: int
    status: str


class CreatureSummary(Api):
    """Codex card payload (spec §14: thumbnail, name, rarity, wins, favorite)."""

    id: int
    name: str
    title: str
    rarity: str
    role: str
    sources: list[str]
    core_stats: dict
    record_status: str = "complete"
    image_status: str
    ability_names: list[str] = Field(
        default_factory=list,
        description="Streaming preview: ability names revealed so far while record_status=generating",
    )
    signature_ability: str = Field(
        default="", description="First ability name — carousel headline without a detail fetch"
    )
    hero_image_path: str | None = None
    thumb_path: str | None = None
    favorite: bool
    wins: int
    losses: int
    championships: int
    created_at: datetime | None = None


class CreatureDetail(CreatureSummary):
    abilities: list[dict]
    strengths: list[str]
    weaknesses: list[str]
    environment_affinities: dict
    fun_fact: str
    anatomy_plan: str
    visual_spec: str
    records: dict
    win_rate: int = 0


class RenameResponse(Api):
    creature_id: int
    name: str
    title: str


class FavoriteResponse(Api):
    creature_id: int
    favorite: bool


class SourceCreature(Api):
    slug: str
    name: str
    category: str = "living"
    contribution: str = Field(default="", description="What this part adds, child-facing")
    blurb: str = ""
    traits: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    art: str | None = None
    aliases: list[str] = Field(
        default_factory=list,
        description="Authored misspellings and nicknames the picker search accepts",
    )
    custom: bool = Field(
        default=False, description="True for parts Henry summoned (custom_parts table)"
    )


class Environment(Api):
    slug: str
    name: str
    blurb: str = ""
    art: str | None = None


class LibraryResponse(Api):
    sources: list[SourceCreature]
    environments: list[Environment]
    loaded: bool = Field(description="False when the data files are not on disk yet")


# -- summon (POST /api/library/summon) ----------------------------------------

class SummonResolution(Strict):
    """The gpt-5.1 summon-resolver contract (strict structured output, so every
    field is required — unused fields come back as "" / [])."""

    decision: Literal["library", "new", "redirect"]
    library_slugs: list[str] = Field(
        description="decision=library: the matching library slug(s), 1-3 of them"
    )
    name: str = Field(description="decision=new: Title Case creature name, max 3 words")
    category: Literal["mythic", "extinct", "living"]
    blurb: str = Field(description="decision=new: one exciting kid-readable sentence")
    traits: list[str] = Field(description="decision=new: exactly 3 short powers/features")
    contribution: str = Field(
        description="decision=new: one sentence starting with 'Adds' — what it gives a chimera"
    )
    portrait_description: str = Field(
        description="decision=new: complete physical description for the portrait painter"
    )
    redirect_message: str = Field(
        description="decision=redirect: one kind playful line steering back to animals"
    )


class SummonRequest(Api):
    query: str = Field(min_length=1, max_length=80)


class SummonResponse(Api):
    status: Literal["matched", "disambiguate", "conjured", "redirect"]
    source: SourceCreature | None = None
    candidates: list[SourceCreature] = Field(default_factory=list)
    message: str = ""
    portrait_status: str = Field(
        default="", description="conjured only: rendering | complete | failed"
    )


# -- tournaments --------------------------------------------------------------

class CreateTournamentRequest(Api):
    entrant_ids: list[int] = Field(min_length=8, max_length=8)
    name: str | None = None


class BracketMatch(Api):
    id: str
    a: int | None = None
    b: int | None = None
    winner: int | None = None
    battle_id: int | None = None
    environment: str
    predicted: int | None = None
    prediction_correct: bool | None = None


class BracketRound(Api):
    name: str
    matches: list[BracketMatch]


class TournamentView(Api):
    id: int
    name: str
    status: str
    entrant_ids: list[int]
    rounds: list[BracketRound]
    champion_id: int | None = None
    entrants: list[CreatureSummary] = Field(default_factory=list)
    created_at: datetime | None = None
    completed_at: datetime | None = None


class PredictRequest(Api):
    pick_id: int


class BattleView(Api):
    """What the Battle screen renders (spec §17 screen 5)."""

    battle_id: int
    match_id: str
    creature_a_id: int
    creature_b_id: int
    environment: str
    winner_id: int
    confidence: float
    reasons: list[BattleReason]
    narrative: str
    beats: list[str]
    health_remaining: HealthRemaining
    predicted: int | None = None
    prediction_correct: bool | None = None
    cached: bool = Field(default=False, description="True when replayed from the determinism cache")


class ResolveResponse(Api):
    battle: BattleView
    tournament: TournamentView


# -- profile & hall -----------------------------------------------------------

class ProfileView(Api):
    name: str
    avatar: str
    level: int
    xp: int
    xp_to_next: int
    settings: dict
    total_creatures: int
    battles_won: int
    biggest_creature: CreatureSummary | None = None
    current_champion: CreatureSummary | None = None
    favorites: list[CreatureSummary] = Field(default_factory=list)


class HallRecord(Api):
    key: str
    label: str
    value: str
    creature: CreatureSummary | None = None


class HallView(Api):
    champions: list[CreatureSummary]
    top_winners: list[CreatureSummary]
    records: list[HallRecord]
