"""Cache headers for the static mounts (added 2026-09-20).

Nothing under /media or /assets carried a Cache-Control header, so Safari
fell back to heuristic freshness (a tenth of the file's age) and re-validated
the 160 picker portraits, every icon and every hero on nearly every screen —
one conditional request per image through the Railway edge. On Henry's iPad
that round-trip storm was a large part of "the app feels slow".

  /assets/*   painted art, icons, the content-hashed Vite bundle   7 days
  /media/*    generated renders: written once, overwritten only by a
              deliberate repaint of a part that had no art             7 days
  /           the SPA shell: never cached, so a deploy shows on the next
              open (the bundle it references is hashed, so it can cache)

stale-while-revalidate keeps the day-eight load instant too: Safari paints
the cached file and refreshes it in the background. Pure ASGI, like the PIN
gate, so /media streaming passes through untouched. Only 200/304 answers get
the header — a 401 from the gate or a 404 must never be cached.
"""
from __future__ import annotations

CACHED_PREFIXES = ("/assets/", "/media/")
LONG_LIVED = b"public, max-age=604800, stale-while-revalidate=2592000"
SHELL = b"no-cache"


class StaticCacheMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path: str = scope["path"]
        if path.startswith(CACHED_PREFIXES):
            value = LONG_LIVED
        elif path in ("/", "/index.html"):
            value = SHELL
        else:
            return await self.app(scope, receive, send)

        async def send_with_cache_control(message):
            if message["type"] == "http.response.start" and message["status"] in (200, 304):
                headers = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"
                ]
                headers.append((b"cache-control", value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cache_control)
