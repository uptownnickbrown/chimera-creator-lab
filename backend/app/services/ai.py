"""Shared OpenAI client + model roster (docs/AI_CONTRACTS.md).

OpenAI-only by decision (no runtime degradation path): if the key is missing
or CHIMERA_STUB_AI=1, callers fall back to the deterministic local stubs —
that mode exists for tests and keyless dev, not as a product feature.
"""
from __future__ import annotations

import logging
import os

from ..config import REPO_ROOT

log = logging.getLogger("chimera.ai")

TEXT_MODEL = "gpt-5.1"
IMAGE_MODEL = "gpt-image-1.5"

_client = None


def _load_env_file() -> None:
    env = REPO_ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)


def ai_enabled() -> bool:
    if os.environ.get("CHIMERA_STUB_AI") == "1":
        return False
    _load_env_file()
    return bool(os.environ.get("OPEN_AI_API_KEY"))


def client():
    """Lazy singleton AsyncOpenAI client."""
    global _client
    if _client is None:
        _load_env_file()
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=os.environ["OPEN_AI_API_KEY"], timeout=300)
    return _client


async def structured(system: str, user: str, model_cls, *, name: str):
    """One structured-output call -> validated pydantic instance.

    No temperature knob: no caller ever used it, and battle determinism is
    owned by the permanent cache (first resolution wins), not by sampling.
    """
    import json

    schema = model_cls.model_json_schema()
    resp = await client().chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        response_format={"type": "json_schema",
                         "json_schema": {"name": name, "strict": True,
                                         "schema": schema}},
    )
    return model_cls.model_validate(json.loads(resp.choices[0].message.content))
