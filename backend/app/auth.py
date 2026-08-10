"""PIN gate. One shared code (Henry's), no accounts, no user table.

The app is public on Railway and every creature POST fans out to OpenAI, so an
unauthenticated stranger is a real dollar cost. The gate is deliberately tiny:

  * POST /api/auth/login  {"pin": "..."}  -> sets a signed session cookie
  * GET  /api/auth/me                     -> 200 if the cookie is valid, else 401
  * GateMiddleware                        -> 401 {"detail": "locked"} on every
                                             /api/* and /media/* request without
                                             a valid cookie

The session cookie is stateless: "<expiry-unix-ts>.<hmac-sha256>" signed with
CHIMERA_SESSION_SECRET (or a key derived from CHIMERA_PIN when the secret is
unset). Nothing to store, nothing to sweep; restarting the process keeps
everyone logged in.

If CHIMERA_PIN itself is unset/empty the whole gate is DISABLED — local dev,
docker-compose and the test suite keep working unchanged.

stdlib only (hmac/hashlib/time): no new dependencies.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.responses import JSONResponse

log = logging.getLogger("chimera.auth")

COOKIE_NAME = "chimera_session"
SESSION_TTL = 180 * 24 * 60 * 60  # ~180 days, seconds

# Login endpoints must stay reachable while locked; everything else under
# /api and /media is guarded. The health probes (/health, /healthz, /readyz)
# live at the root — outside /api and /media — so the guard never sees them.
EXEMPT_PATHS = {"/api/auth/login", "/api/auth/me"}

# -- token ---------------------------------------------------------------------


def _pin() -> str:
    """Read at request time (not import time) so tests and ops can flip the
    env var without rebuilding the app object."""
    return os.environ.get("CHIMERA_PIN", "")


def _key() -> bytes:
    secret = os.environ.get("CHIMERA_SESSION_SECRET", "")
    if secret:
        return secret.encode()
    # Fallback: derive a signing key from the PIN. Weaker (rotating the PIN
    # logs everyone out, and the PIN is low-entropy) but keeps single-var
    # setups working. Set CHIMERA_SESSION_SECRET in prod.
    return hashlib.sha256(b"chimera-gate-v1:" + _pin().encode()).digest()


def _sign(msg: str) -> str:
    return hmac.new(_key(), msg.encode(), hashlib.sha256).hexdigest()


def mint_token(now: float | None = None) -> str:
    exp = int((now if now is not None else time.time()) + SESSION_TTL)
    return f"{exp}.{_sign(str(exp))}"


def token_valid(token: str) -> bool:
    exp_s, _, sig = token.partition(".")
    if not sig or not exp_s.isdigit():
        return False
    if int(exp_s) < time.time():
        return False
    return hmac.compare_digest(sig, _sign(exp_s))


# -- login rate limit ----------------------------------------------------------
# Single-instance app (one Railway container), so a process-local dict is the
# whole database. {client_ip: [failure timestamps within the window]}.

MAX_FAILURES = 10
WINDOW_SECONDS = 5 * 60
_failures: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    # Railway terminates TLS at its proxy; the real client is the first hop
    # of X-Forwarded-For. Direct connections (dev) fall back to the socket.
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _too_many_failures(ip: str, now: float) -> bool:
    recent = [t for t in _failures.get(ip, ()) if now - t < WINDOW_SECONDS]
    if recent:
        _failures[ip] = recent
    else:
        _failures.pop(ip, None)
    if len(_failures) > 1000:  # bounded memory even under a spray of IPs
        for stale in [k for k, v in _failures.items() if now - v[-1] >= WINDOW_SECONDS]:
            _failures.pop(stale, None)
    return len(recent) >= MAX_FAILURES


# -- routes --------------------------------------------------------------------

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    pin: str = ""


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response) -> dict:
    pin = _pin()
    if not pin:
        return {"ok": True}  # gate disabled — nothing to check, no cookie needed

    ip = _client_ip(request)
    now = time.time()
    if _too_many_failures(ip, now):
        raise HTTPException(
            status_code=429,
            detail="Whoa, too many tries! The lab door needs a 5 minute rest.",
        )

    if not hmac.compare_digest(body.pin.encode(), pin.encode()):
        _failures.setdefault(ip, []).append(now)
        log.info("gate: wrong PIN from %s (%d recent failures)", ip, len(_failures[ip]))
        raise HTTPException(status_code=401, detail="wrong code")

    _failures.pop(ip, None)
    response.set_cookie(
        COOKIE_NAME,
        mint_token(now),
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
        path="/",
        # Deliberately NOT Secure: the QA loop and local dev authenticate
        # through the http://localhost vite proxy, and a Secure cookie would
        # silently never come back there. Tradeoff accepted — the cookie only
        # guards a kids' game, and prod traffic is HTTPS end-to-end anyway.
        secure=False,
    )
    return {"ok": True}


@router.get("/me")
async def me(request: Request) -> dict:
    if not _pin():
        return {"ok": True, "gate": "disabled"}
    if token_valid(request.cookies.get(COOKIE_NAME, "")):
        return {"ok": True}
    raise HTTPException(status_code=401, detail="locked")


# -- middleware ----------------------------------------------------------------


class GateMiddleware:
    """Pure ASGI guard over /api/* and /media/*.

    Pure ASGI (not BaseHTTPMiddleware) so /media file streaming passes through
    untouched. Everything outside /api and /media — the SPA shell, health
    probes — stays public; all data and generated art is behind the PIN.
    """

    def __init__(self, app):
        self.app = app
        if not _pin():
            log.warning(
                "CHIMERA_PIN is not set — the PIN gate is DISABLED and the API "
                "is open. Fine for dev/tests; set CHIMERA_PIN in production."
            )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path: str = scope["path"]
        guarded = path.startswith(("/api/", "/media/")) or path in ("/api", "/media")
        if (
            not guarded
            or path in EXEMPT_PATHS
            or scope["method"] == "OPTIONS"  # CORS preflight carries no cookies
            or not _pin()  # gate disabled
            or token_valid(self._cookie(scope))
        ):
            return await self.app(scope, receive, send)

        response = JSONResponse({"detail": "locked"}, status_code=401)
        await response(scope, receive, send)

    @staticmethod
    def _cookie(scope) -> str:
        raw = b"; ".join(v for k, v in scope["headers"] if k == b"cookie").decode("latin-1")
        for part in raw.split(";"):
            name, _, value = part.strip().partition("=")
            if name == COOKIE_NAME:
                return value.strip('"')
        return ""
