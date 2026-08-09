"""initial schema

Every table as of the first Postgres deploy: profiles, creatures, custom_parts,
battles, tournaments.

Portability notes (this migration must run on Postgres AND SQLite):
- JSON columns use the same `with_variant` as models.py: JSONB on Postgres,
  plain JSON on SQLite.
- Enums are `native_enum=False`, i.e. VARCHAR + CHECK on both backends. No
  Postgres ENUM types are created, so adding a value later is a code change
  only — no ALTER TYPE, and no enum left behind on downgrade.
- `created_at` defaults use `sa.func.now()` (not a literal `now()`), which
  compiles to `now()` on Postgres and `CURRENT_TIMESTAMP` on SQLite.

Revision ID: d71354bd48b7
Revises:
Create Date: 2026-08-09 15:13:16.736399
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d71354bd48b7"
down_revision = None
branch_labels = None
depends_on = None


def _json() -> sa.types.TypeEngine:
    """Mirror of models.JSON — JSONB on Postgres, JSON everywhere else."""
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("avatar", sa.String(length=120), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False),
        sa.Column("settings", _json(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "creatures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("sources", _json(), nullable=False),
        sa.Column("rarity", sa.String(length=24), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("core_stats", _json(), nullable=False),
        sa.Column("abilities", _json(), nullable=False),
        sa.Column("strengths", _json(), nullable=False),
        sa.Column("weaknesses", _json(), nullable=False),
        sa.Column("environment_affinities", _json(), nullable=False),
        sa.Column("sim_profile", _json(), nullable=False),
        sa.Column("visual_spec", sa.Text(), nullable=False),
        sa.Column("anatomy_plan", sa.Text(), nullable=False),
        sa.Column("fun_fact", sa.Text(), nullable=False),
        sa.Column(
            "record_status",
            sa.Enum("generating", "complete", "failed", name="record_status", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "image_status",
            sa.Enum("pending", "complete", "failed", name="image_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("hero_image_path", sa.String(length=255), nullable=True),
        sa.Column("thumb_path", sa.String(length=255), nullable=True),
        sa.Column("favorite", sa.Boolean(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("losses", sa.Integer(), nullable=False),
        sa.Column("championships", sa.Integer(), nullable=False),
        sa.Column("records", _json(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_creatures_name", "creatures", ["name"], unique=False)

    op.create_table(
        "custom_parts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("blurb", sa.Text(), nullable=False),
        sa.Column("contribution", sa.Text(), nullable=False),
        sa.Column("traits", _json(), nullable=False),
        sa.Column("aliases", _json(), nullable=False),
        sa.Column("portrait_description", sa.Text(), nullable=False),
        sa.Column(
            "portrait_status",
            sa.Enum("pending", "complete", "failed", name="portrait_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("art", sa.String(length=255), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_parts_slug", "custom_parts", ["slug"], unique=True)

    op.create_table(
        "battles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("creature_a_id", sa.Integer(), nullable=False),
        sa.Column("creature_b_id", sa.Integer(), nullable=False),
        sa.Column("environment", sa.String(length=48), nullable=False),
        sa.Column("winner_id", sa.Integer(), nullable=False),
        sa.Column("reasons", _json(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("beats", _json(), nullable=False),
        sa.Column("health_remaining", _json(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("canonical_key", sa.String(length=96), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["creature_a_id"], ["creatures.id"]),
        sa.ForeignKeyConstraint(["creature_b_id"], ["creatures.id"]),
        sa.ForeignKeyConstraint(["winner_id"], ["creatures.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # canonical_key is the determinism cache key — uniqueness is load-bearing.
    op.create_index("ix_battles_canonical_key", "battles", ["canonical_key"], unique=True)
    op.create_index("ix_battles_creature_a_id", "battles", ["creature_a_id"], unique=False)
    op.create_index("ix_battles_creature_b_id", "battles", ["creature_b_id"], unique=False)
    op.create_index("ix_battles_winner_id", "battles", ["winner_id"], unique=False)

    op.create_table(
        "tournaments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "status",
            sa.Enum("setup", "active", "complete", name="tournament_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("entrant_ids", _json(), nullable=False),
        sa.Column("bracket", _json(), nullable=False),
        sa.Column("champion_id", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["champion_id"], ["creatures.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("tournaments")
    op.drop_index("ix_battles_winner_id", table_name="battles")
    op.drop_index("ix_battles_creature_b_id", table_name="battles")
    op.drop_index("ix_battles_creature_a_id", table_name="battles")
    op.drop_index("ix_battles_canonical_key", table_name="battles")
    op.drop_table("battles")
    op.drop_index("ix_custom_parts_slug", table_name="custom_parts")
    op.drop_table("custom_parts")
    op.drop_index("ix_creatures_name", table_name="creatures")
    op.drop_table("creatures")
    op.drop_table("profiles")
