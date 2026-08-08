"""Persistent entities — all tables in one file (Agora convention).

Conventions:
- Single player, so no tenancy column anywhere. `Profile` is a single row.
- Child-facing stats live in `core_stats` (0-100); the richer simulation view
  lives in `sim_profile`. Never show sim_profile in the UI (spec §12, §18).
- `Battle.canonical_key` is "minCreatureId:maxCreatureId:environment" and is
  UNIQUE. It is the permanent determinism cache: a matchup is reasoned about
  once and replayed from the row forever after (ARCHITECTURE.md "Determinism").
- JSON columns hold pydantic-validated blobs (see schemas.py). Mutate them by
  assigning a fresh object, never in place — SQLAlchemy will not see in-place
  edits to a plain JSON column.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class ImageStatus(str, enum.Enum):
    pending = "pending"
    complete = "complete"
    failed = "failed"


class TournamentStatus(str, enum.Enum):
    setup = "setup"
    active = "active"
    complete = "complete"


def _enum(py_enum, name: str):
    # native_enum=False keeps SQLite and Postgres on the same VARCHAR + CHECK
    # shape, so no ALTER TYPE dance when a value is added later.
    return SAEnum(
        py_enum, name=name, native_enum=False,
        values_callable=lambda e: [m.value for m in e],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# -- player -------------------------------------------------------------------

class Profile(TimestampMixin, Base):
    """Exactly one row (id=1). Henry's identity, level, and preferences."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), default="Henry")
    avatar: Mapped[str] = mapped_column(String(120), default="avatars/henry")
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


# -- creatures ----------------------------------------------------------------

class Creature(TimestampMixin, Base):
    """One generated chimera plus its accumulated arena history."""

    __tablename__ = "creatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(160), default="")
    sources: Mapped[list] = mapped_column(JSON, default=list)  # 4 source-creature slugs
    rarity: Mapped[str] = mapped_column(String(24), default="Rare")
    role: Mapped[str] = mapped_column(String(80), default="")

    core_stats: Mapped[dict] = mapped_column(JSON, default=dict)  # child-facing, 0-100
    abilities: Mapped[list] = mapped_column(JSON, default=list)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)
    environment_affinities: Mapped[dict] = mapped_column(JSON, default=dict)  # -2..+2
    sim_profile: Mapped[dict] = mapped_column(JSON, default=dict)  # hidden, 0-100

    visual_spec: Mapped[str] = mapped_column(Text, default="")
    anatomy_plan: Mapped[str] = mapped_column(Text, default="")
    fun_fact: Mapped[str] = mapped_column(Text, default="")

    image_status: Mapped[ImageStatus] = mapped_column(
        _enum(ImageStatus, "image_status"), default=ImageStatus.pending
    )
    hero_image_path: Mapped[str | None] = mapped_column(String(255))
    thumb_path: Mapped[str | None] = mapped_column(String(255))

    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    championships: Mapped[int] = mapped_column(Integer, default=0)
    records: Mapped[dict] = mapped_column(JSON, default=dict)  # "Biggest Win", "Fastest Win", ...


# -- battles ------------------------------------------------------------------

class Battle(TimestampMixin, Base):
    """A resolved matchup. One row per (creature pair, environment), forever.

    `canonical_key` is unique; service code normalizes the pair to (min, max) so
    (A vs B) and (B vs A) collapse onto the same row and therefore the same
    winner. See services/battle.py.
    """

    __tablename__ = "battles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    creature_a_id: Mapped[int] = mapped_column(ForeignKey("creatures.id"), index=True)
    creature_b_id: Mapped[int] = mapped_column(ForeignKey("creatures.id"), index=True)
    environment: Mapped[str] = mapped_column(String(48))
    winner_id: Mapped[int] = mapped_column(ForeignKey("creatures.id"), index=True)

    reasons: Mapped[list] = mapped_column(JSON, default=list)  # exactly 3 {icon,title,blurb}
    narrative: Mapped[str] = mapped_column(Text, default="")
    beats: Mapped[list] = mapped_column(JSON, default=list)  # 4-6 short strings
    health_remaining: Mapped[dict] = mapped_column(JSON, default=dict)  # {"a": int, "b": int}
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    canonical_key: Mapped[str] = mapped_column(String(96), unique=True, index=True)


# -- tournaments --------------------------------------------------------------

class Tournament(TimestampMixin, Base):
    """8-entrant bracket: quarterfinals -> semifinals -> championship.

    `bracket` shape:
      {"rounds": [{"name": "Quarterfinals",
                   "matches": [{"id": "r0m0", "a": 1, "b": 2, "winner": null,
                                "battle_id": null, "environment": "deep_ocean",
                                "predicted": null, "prediction_correct": null}, ...]}, ...]}
    """

    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), default="Arena Tournament")
    status: Mapped[TournamentStatus] = mapped_column(
        _enum(TournamentStatus, "tournament_status"), default=TournamentStatus.setup
    )
    entrant_ids: Mapped[list] = mapped_column(JSON, default=list)  # exactly 8 creature ids
    bracket: Mapped[dict] = mapped_column(JSON, default=dict)
    champion_id: Mapped[int | None] = mapped_column(ForeignKey("creatures.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
