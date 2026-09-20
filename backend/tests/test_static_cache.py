"""Static delivery (2026-09-20): long-lived Cache-Control on /media and /assets,
a real image/webp content type, and nothing cacheable on the API or on a
gate refusal. The iPad re-validated every portrait on every screen without
these."""
from __future__ import annotations

from pathlib import Path


def _media_mount_dir() -> Path:
    """The directory the /media mount actually serves (bound at import time,
    so it may predate this test's own settings)."""
    from app.main import app

    mount = next(r for r in app.routes if getattr(r, "path", None) == "/media")
    return Path(mount.app.directory)


async def test_media_files_are_cacheable_webp(client):
    parts = _media_mount_dir() / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    (parts / "custom_cache-fox.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ")

    r = await client.get("/media/parts/custom_cache-fox.webp")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/webp"
    assert r.headers["cache-control"] == "public, max-age=604800, stale-while-revalidate=2592000"

    # A conditional re-fetch renews freshness too.
    r2 = await client.get("/media/parts/custom_cache-fox.webp", headers={"if-none-match": r.headers["etag"]})
    assert r2.status_code == 304
    assert r2.headers["cache-control"].startswith("public, max-age=604800")


async def test_missing_media_and_api_answers_are_not_cacheable(client):
    r = await client.get("/media/parts/custom_never-painted.webp")
    assert r.status_code == 404
    assert "cache-control" not in r.headers

    r = await client.get("/api/library")
    assert r.status_code == 200
    assert "cache-control" not in r.headers


async def test_gate_refusal_is_not_cacheable(client, monkeypatch):
    monkeypatch.setenv("CHIMERA_PIN", "4242")
    r = await client.get("/media/parts/custom_cache-fox.webp")
    assert r.status_code == 401
    assert "cache-control" not in r.headers
