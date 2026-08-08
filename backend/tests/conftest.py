"""Test harness: a throwaway SQLite file per test, driven through the real app."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("CHIMERA_DATA_DIR", str(tmp_path / "data"))  # deliberately absent
    monkeypatch.setenv("CHIMERA_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("CHIMERA_STUB_AI", "1")  # tests never touch the network

    from app import config
    from app import db as dbmod
    from app.main import app
    from app.services import library as library_svc

    config.get_settings.cache_clear()
    dbmod._engine = None
    dbmod._session_factory = None

    # ASGITransport does not run lifespan, so do its two jobs here.
    await dbmod.create_all()
    library_svc.load_library()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await dbmod.engine().dispose()
    dbmod._engine = None
    dbmod._session_factory = None
    config.get_settings.cache_clear()


SOURCE_SETS = [
    ["dragon", "stegosaurus", "electric_eel", "shark"],
    ["kraken", "woolly_mammoth", "chameleon", "peregrine_falcon"],
    ["griffin", "triceratops", "cobra", "octopus"],
    ["phoenix", "sabertooth", "tiger", "bat"],
    ["hydra", "pterodactyl", "rhino", "jellyfish"],
    ["basilisk", "megalodon", "eagle", "scorpion"],
    ["minotaur", "velociraptor", "wolf", "crab"],
    ["leviathan", "mammoth", "gorilla", "hornet"],
]


async def make_creature(client: AsyncClient, index: int = 0) -> dict:
    """Create one chimera and return its full record."""
    sources = SOURCE_SETS[index % len(SOURCE_SETS)]
    created = await client.post("/api/creatures", json={"source_slugs": sources})
    assert created.status_code == 200, created.text
    got = await client.get(f"/api/creatures/{created.json()['creature_id']}")
    assert got.status_code == 200, got.text
    return got.json()


async def make_roster(client: AsyncClient, count: int = 8) -> list[dict]:
    return [await make_creature(client, i) for i in range(count)]
