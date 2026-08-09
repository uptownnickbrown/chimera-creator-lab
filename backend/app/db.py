"""Async engine/session plumbing (Agora convention: thin, no ORM magic)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or get_settings().database_url
    if url.startswith("sqlite") and ":memory:" not in url:
        # SQLite under concurrent background tasks (observed 2026-08-09: a
        # creature stranded at "generating" because its session open blocked
        # while other work held the database):
        # - NullPool: a fresh connection per session — no pool-checkout waits.
        # - WAL: readers and writers never block each other.
        # - Bounded busy wait: real contention raises loudly, never hangs.
        from sqlalchemy import event
        from sqlalchemy.pool import NullPool

        eng = create_async_engine(url, poolclass=NullPool, connect_args={"timeout": 15})

        @event.listens_for(eng.sync_engine, "connect")
        def _sqlite_tune(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()

        return eng
    if url.startswith("sqlite"):
        return create_async_engine(url)
    return create_async_engine(url, pool_pre_ping=True)


def make_session_factory(engine=None) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine or make_engine(), expire_on_commit=False)


# Module-level singletons for the running app. Tests override the dependency.
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def engine():
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = make_session_factory(engine())
    return _session_factory


async def create_all() -> None:
    """Dev convenience: stand the schema up in place. Postgres uses alembic."""
    from . import models  # noqa: F401  (import for metadata registration)

    async with engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, commit on clean exit."""
    async with session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
