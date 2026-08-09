"""Runtime settings. Single-player game, so knobs stay few and env-driven."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# repo root = .../chimera-creator (backend/app/config.py -> up three)
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    # SQLite for dev/test; Railway injects a Postgres DATABASE_URL in prod.
    # The default is ABSOLUTE on purpose. A relative "./chimera.db" resolves
    # against the process's working directory, so starting uvicorn from
    # backend/ instead of the repo root silently opened a DIFFERENT, empty
    # database — which then looked like a first run and let the starter seeder
    # write its art over the real player's media. One repo, one dev database,
    # wherever you launch from.
    database_url: str = field(
        default_factory=lambda: _normalize_db_url(
            os.environ.get("DATABASE_URL", f"sqlite+aiosqlite:///{REPO_ROOT / 'chimera.db'}")
        )
    )
    env: str = field(default_factory=lambda: os.environ.get("CHIMERA_ENV", "dev"))
    cors_origins: str = field(
        default_factory=lambda: os.environ.get(
            "CHIMERA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        )
    )
    # Directory holding source_creatures.json / environments.json. Another agent
    # owns these files; the app must boot fine before they land.
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("CHIMERA_DATA_DIR", str(REPO_ROOT / "data")))
    )
    player_name: str = field(default_factory=lambda: os.environ.get("CHIMERA_PLAYER", "Henry"))
    # Backend-owned generated media (hero renders, thumbs, finals key art),
    # served at /media. On Railway this should point at a persistent volume.
    media_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("CHIMERA_MEDIA_DIR", str(REPO_ROOT / "media")))
    )


def _normalize_db_url(url: str) -> str:
    """Accept the plain URLs hosting providers hand out and make them async."""
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    elif url.startswith("sqlite:///"):
        url = "sqlite+aiosqlite:///" + url[len("sqlite:///") :]
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
