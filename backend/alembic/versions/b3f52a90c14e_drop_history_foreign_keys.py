"""drop the history foreign keys

The initial migration gave battles.creature_{a,b}_id, battles.winner_id and
tournaments.champion_id foreign keys to creatures.id. The models never had
them, and deliberately so: a creature is deletable in any state (the playtest
rule is "creatable => deletable"), while its battles are the permanent
determinism cache and its tournaments are history. Both keep the raw id and
render a deleted creature as a ghost.

So those constraints were a real production bug, not a style difference. On
SQLite `create_all` builds the schema and no FK exists, which is why local
deletes always worked; on the Postgres that `alembic upgrade head` builds,
deleting a creature with any battle history would have raised a foreign key
violation. CI caught it as an `alembic check` drift before Henry's data moved
up. This migration removes them so both backends match the models.

Portability: Postgres can drop a constraint by its auto-generated name
(`<table>_<column>_fkey`); SQLite cannot drop a constraint at all, so the two
tables are rebuilt through batch mode from an explicit FK-free definition.
The definitions below are copied verbatim from the initial migration (minus the
ForeignKeyConstraint lines) and are frozen at that point in time on purpose — a
later schema change gets its own migration, not an edit here. They carry the
indexes too: a batch rebuild drops the old table, and with `copy_from` alembic
recreates only what the passed definition declares, so an index left out here
would silently disappear.

Revision ID: b3f52a90c14e
Revises: d71354bd48b7
Create Date: 2026-08-09 19:45:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b3f52a90c14e"
down_revision = "d71354bd48b7"
branch_labels = None
depends_on = None

# The four constraints, as ("table", "column"). Postgres names them
# "<table>_<column>_fkey" when they are created unnamed inside a CREATE TABLE.
HISTORY_FKS = [
    ("battles", "creature_a_id"),
    ("battles", "creature_b_id"),
    ("battles", "winner_id"),
    ("tournaments", "champion_id"),
]


def _json() -> sa.types.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _battles(*extra: sa.schema.SchemaItem) -> sa.Table:
    return sa.Table(
        "battles",
        sa.MetaData(),
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
        sa.PrimaryKeyConstraint("id"),
        # canonical_key is the determinism cache key — uniqueness is load-bearing.
        sa.Index("ix_battles_canonical_key", "canonical_key", unique=True),
        sa.Index("ix_battles_creature_a_id", "creature_a_id"),
        sa.Index("ix_battles_creature_b_id", "creature_b_id"),
        sa.Index("ix_battles_winner_id", "winner_id"),
        *extra,
    )


def _tournaments(*extra: sa.schema.SchemaItem) -> sa.Table:
    return sa.Table(
        "tournaments",
        sa.MetaData(),
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
        sa.PrimaryKeyConstraint("id"),
        *extra,
    )


def _creature_fks(table: str) -> list[sa.ForeignKeyConstraint]:
    return [sa.ForeignKeyConstraint([col], ["creatures.id"])
            for tbl, col in HISTORY_FKS if tbl == table]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # The names are looked up rather than assumed. Postgres does call these
        # "<table>_<column>_fkey" (verified against a real 16 instance), but the
        # container runs `alembic upgrade head` at boot: a drop of a name that
        # isn't there would crash the app on start, so a database that never had
        # the constraint simply skips it.
        inspector = sa.inspect(bind)
        for table, column in HISTORY_FKS:
            for fk in inspector.get_foreign_keys(table):
                if fk["constrained_columns"] == [column] and fk["name"]:
                    op.drop_constraint(fk["name"], table, type_="foreignkey")
        return

    # SQLite: batch mode rebuilds each table from `copy_from`, and the copy has
    # no foreign keys, so they simply do not come back. recreate="always" is
    # required — the default "auto" only rebuilds when an operation inside the
    # block demands it, and there are no operations here; the rebuild IS the
    # operation.
    with op.batch_alter_table("battles", copy_from=_battles(), recreate="always"):
        pass
    with op.batch_alter_table("tournaments", copy_from=_tournaments(), recreate="always"):
        pass


def downgrade() -> None:
    """Restore the four constraints — only possible if the data still satisfies them.

    Once a creature with battle history has been deleted, its battles are orphan
    rows by design and re-adding the constraint fails (cleanly, inside alembic's
    transaction). That is the migration telling the truth: going back means
    losing that history.
    """
    if op.get_bind().dialect.name == "postgresql":
        for table, column in HISTORY_FKS:
            op.create_foreign_key(f"{table}_{column}_fkey", table, "creatures",
                                  [column], ["id"])
        return

    with op.batch_alter_table("battles", copy_from=_battles(*_creature_fks("battles")),
                              recreate="always"):
        pass
    with op.batch_alter_table("tournaments",
                              copy_from=_tournaments(*_creature_fks("tournaments")),
                              recreate="always"):
        pass
