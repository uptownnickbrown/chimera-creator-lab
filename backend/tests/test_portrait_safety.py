"""The image safety filter vs. Henry's Pokémon (Railway logs, 2026-09-19/20).

gpt-image-1.5 refuses prompts that name famous trademarked characters, and a
retry of the identical prompt is doomed. These tests pin the fix: a rejected
prompt is never re-sent, the fallback prompt is anatomy only (no name, no
franchise words), transient errors still retry, and the boot resweep heals
the parts that were stranded before the fallback existed. No network: the
image call is a scripted fake and the LLM rewrite is the regex scrub.
"""
from __future__ import annotations

import asyncio
import io
from types import SimpleNamespace

from PIL import Image, ImageDraw
from sqlalchemy import select
from test_summon import author_library

#: Verbatim shape of the prod rejection (str(openai.BadRequestError)).
SAFETY_MSG = (
    "Error code: 400 - {'error': {'message': 'Your request was rejected by the safety "
    "system. If you believe this is an error, contact us at help.openai.com and include "
    "the request ID req_abc123', 'type': 'user_error', 'param': None, "
    "'code': 'moderation_blocked'}}"
)


def ellipse_png(box=(200, 300, 700, 900), size=(1024, 1024)) -> bytes:
    """A transparent canvas with one opaque ellipse: what a render looks like."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse(box, fill=(255, 120, 0, 255))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def alpha_bbox_size(data: bytes) -> tuple[int, int]:
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    left, top, right, bottom = img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    return (right - left, bottom - top)


def arm_real_ladder(monkeypatch) -> None:
    """AI 'on' with no network: the LLM rewrite is the regex scrub, backoff is instant."""
    from app.services import ai, images

    monkeypatch.setattr(ai, "ai_enabled", lambda: True)

    async def scrub(text, names):
        return images.debrand(text, names)

    async def no_wait(attempt):
        return None

    async def reimagine(text, names, *, distance="close"):
        lead = "A close cousin: " if distance == "close" else "A distant cousin: "
        return lead + images.debrand(text, names)

    monkeypatch.setattr(images, "debrand_via_llm", scrub)
    monkeypatch.setattr(images, "reimagine_via_llm", reimagine)
    monkeypatch.setattr(images, "_backoff", no_wait)


class FakeRender:
    """Scripted images._render: each step is PNG bytes (success) or an exception."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls: list[dict] = []

    async def __call__(self, prompt, *, quality, size=None):
        self.calls.append({"prompt": prompt, "quality": quality, "size": size})
        step = self.script.pop(0) if self.script else RuntimeError("script exhausted")
        if isinstance(step, BaseException):
            raise step
        return step

    @property
    def prompts(self) -> list[str]:
        return [c["prompt"] for c in self.calls]


def hero_creature(**overrides) -> SimpleNamespace:
    base = {
        "id": 4242,
        "name": "Stormfang",
        "visual_spec": (
            "Night Fury-style jet-black dragon with a shark's dorsal fin, four legs, "
            "and cyan bioluminescent seams along the flanks."
        ),
        "sources": ["custom/night-fury", "shark", "dragon", "electric_eel"],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# -- pure functions -------------------------------------------------------------

def test_debrand_scrubs_names_possessives_and_franchise_words():
    from app.services.images import debrand

    text = (
        "Charizard is a Pokémon-like orange dragon with a cream belly, Charizard's "
        "flame-tipped tail, and teal wing membranes straight out of Pokemon. "
        "Night-Fury style jet-black head plates like a Night Fury's, inspired by "
        "How to Train Your Dragon."
    )
    out = debrand(text, ["Charizard", "Night Fury"])
    low = out.lower()
    for banned in ("charizard", "pokémon", "pokemon", "fury", "how to train"):
        assert banned not in low, out
    for kept in ("orange dragon", "cream belly", "the creature's flame-tipped tail",
                 "teal wing membranes", "jet-black head plates"):
        assert kept in low, out
    assert "  " not in out and "like a the creature" not in low, out
    assert out[0].isupper()


def test_debrand_handles_hyphenated_and_bare_names():
    from app.services.images import debrand

    out = debrand("A NightFury with a Night-Fury tail; the famous Godzilla stands tall.",
                  ["Night Fury", "Godzilla"])
    low = out.lower()
    assert "fury" not in low and "godzilla" not in low, out
    assert "tail" in low and "stands tall" in low, out


def test_debrand_leaves_clean_anatomy_alone():
    from app.services.images import debrand

    text = "A stocky armored lizard with copper scales and a club tail."
    assert debrand(text, ["Ankylo Beast"]) == text
    assert debrand("", ["Anything"]) == ""


def test_is_safety_rejection_recognizes_the_prod_message_only():
    from app.services.images import is_safety_rejection

    assert is_safety_rejection(Exception(SAFETY_MSG))
    coded = RuntimeError("no useful message")
    coded.code = "moderation_blocked"
    assert is_safety_rejection(coded)
    assert not is_safety_rejection(
        RuntimeError("Error code: 500 - {'error': {'message': 'The server had an error'}}")
    )
    assert not is_safety_rejection(TimeoutError())
    assert not is_safety_rejection(RuntimeError("script exhausted"))


def test_hero_quality_knob_rejects_garbage(monkeypatch):
    from app import config

    monkeypatch.setenv("CHIMERA_HERO_QUALITY", "ultra")
    monkeypatch.setenv("CHIMERA_KEYART_QUALITY", "Medium")
    config.get_settings.cache_clear()
    try:
        assert config.get_settings().hero_quality == "high"
        assert config.get_settings().keyart_quality == "medium"
    finally:
        config.get_settings.cache_clear()


# -- part portraits -------------------------------------------------------------

async def test_part_portrait_retries_anonymous_after_safety_rejection(client, monkeypatch):
    from app.config import get_settings
    from app.services import images

    arm_real_ladder(monkeypatch)
    png = ellipse_png()
    render = FakeRender(Exception(SAFETY_MSG), png)
    monkeypatch.setattr(images, "_render", render)

    art = await images.generate_part_portrait(
        "custom_charizard", "Charizard",
        "Charizard, the famous Pokémon fire lizard: orange scales, a cream belly, "
        "teal wing membranes, and a flame burning at the tip of its tail.",
        names=["Charizard"],
    )
    assert art == "/media/parts/custom_charizard.webp"
    assert len(render.calls) == 2
    first, second = render.prompts
    assert "Creature: Charizard." in first
    assert "Charizard" not in second and "Creature: " not in second, second
    assert "orange scales" in second and "flame burning" in second, second
    assert second.startswith(images.PART_PORTRAIT_STYLE)
    assert second.endswith(images.PART_PORTRAIT_ISOLATION)
    assert all(c["quality"] == "medium" and c["size"] == "1024x1024" for c in render.calls)

    saved = get_settings().media_dir / "parts" / "custom_charizard.webp"
    assert saved.exists()
    with Image.open(saved) as img:
        assert img.format == "WEBP" and img.mode == "RGBA"
        assert img.size == alpha_bbox_size(png)  # TIGHT: the ellipse's own bbox
        assert img.size[0] < 1024 and img.size[1] < 1024


async def test_part_portrait_never_resends_a_rejected_prompt(client, monkeypatch):
    from app.services import images

    arm_real_ladder(monkeypatch)
    render = FakeRender(Exception(SAFETY_MSG), Exception(SAFETY_MSG), Exception(SAFETY_MSG),
                        Exception(SAFETY_MSG), ellipse_png())
    monkeypatch.setattr(images, "_render", render)

    art = await images.generate_part_portrait(
        "custom_mewtwo", "Mewtwo",
        "Mewtwo: a slim bipedal feline-alien with a lavender body and a thick purple tail.",
        names=["Mewtwo"],
    )
    assert art is None
    # Named, anonymous, cousin, distinct — four different prompts, and never a
    # fifth call on one the filter already refused.
    assert len(render.prompts) == 4 and len(set(render.prompts)) == 4
    assert "A close cousin" in render.prompts[2] and "A distant cousin" in render.prompts[3]


async def test_part_portrait_reimagines_when_the_faithful_rewrite_is_refused(client, monkeypatch):
    """The 2026-09-20 resweep: Blastoise refused with every name gone — the
    filter knows the shell cannons. The third rung redesigns it."""
    from app.services import images

    arm_real_ladder(monkeypatch)
    render = FakeRender(Exception(SAFETY_MSG), Exception(SAFETY_MSG), ellipse_png())
    monkeypatch.setattr(images, "_render", render)

    art = await images.generate_part_portrait(
        "custom_blastoise", "Blastoise",
        "Blastoise: a huge bipedal blue turtle with two water cannons in its shell.",
        names=["Blastoise"],
    )
    assert art == "/media/parts/custom_blastoise.webp"
    named, anonymous, cousin = render.prompts
    assert "Creature: Blastoise." in named
    assert "Blastoise" not in anonymous and "cousin" not in anonymous
    assert "A close cousin" in cousin and "Blastoise" not in cousin
    assert "water cannons" in cousin, "the close rung keeps the creature's own features"
    assert cousin.startswith(images.PART_PORTRAIT_STYLE)


async def test_part_portrait_transient_error_retries_the_same_prompt(client, monkeypatch):
    from app.services import images

    arm_real_ladder(monkeypatch)
    render = FakeRender(RuntimeError("Error code: 500 - server hiccup"), ellipse_png())
    monkeypatch.setattr(images, "_render", render)

    art = await images.generate_part_portrait(
        "custom_zapdos", "Zapdos", "A spiky yellow storm bird with jagged wings.",
        names=["Zapdos"],
    )
    assert art == "/media/parts/custom_zapdos.webp"
    assert render.prompts[0] == render.prompts[1]
    assert "Creature: Zapdos." in render.prompts[0]


async def test_part_portrait_caps_at_four_attempts(client, monkeypatch):
    from app.services import images

    arm_real_ladder(monkeypatch)
    render = FakeRender(RuntimeError("500"), RuntimeError("500"), RuntimeError("500"),
                        RuntimeError("500"), ellipse_png())
    monkeypatch.setattr(images, "_render", render)

    art = await images.generate_part_portrait("custom_x", "Xeno Cat", "A cat.", names=[])
    assert art is None
    assert len(render.calls) == images.PART_PORTRAIT_ATTEMPTS == 4


# -- hero renders ---------------------------------------------------------------

async def test_hero_rewrites_once_and_keeps_the_medium_fallback(client, monkeypatch):
    from app.config import get_settings
    from app.services import images

    arm_real_ladder(monkeypatch)
    png = ellipse_png(size=(1536, 1024))
    render = FakeRender(Exception(SAFETY_MSG), RuntimeError("Error code: 500"), png)
    monkeypatch.setattr(images, "_render", render)

    hero = await images.generate_hero(hero_creature())
    assert hero == "/media/creatures/4242.webp"
    assert [c["quality"] for c in render.calls] == ["high", "high", "medium"]
    p0, p1, p2 = render.prompts
    assert "Night Fury" in p0 and p0.startswith(images.HERO_STYLE)
    assert p1 != p0, "the rejected prompt was re-sent"
    assert p1 == p2, "a transient error must retry the (unrejected) rewritten prompt"
    assert "fury" not in p1.lower() and "night" not in p1.lower(), p1
    assert "jet-black" in p1.lower() and "cyan bioluminescent seams" in p1, p1
    assert p1.startswith(images.HERO_STYLE)
    assert (get_settings().media_dir / "creatures" / "4242.webp").exists()


async def test_hero_gives_up_when_the_rewrite_is_rejected_too(client, monkeypatch):
    from app.services import images

    arm_real_ladder(monkeypatch)
    render = FakeRender(Exception(SAFETY_MSG), Exception(SAFETY_MSG), Exception(SAFETY_MSG),
                        Exception(SAFETY_MSG), ellipse_png(size=(1536, 1024)))
    monkeypatch.setattr(images, "_render", render)

    assert await images.generate_hero(hero_creature()) is None
    assert len(render.prompts) == 4 and len(set(render.prompts)) == 4
    assert "A close cousin" in render.prompts[2] and "A distant cousin" in render.prompts[3]


async def test_hero_third_rung_is_the_reimagined_spec(client, monkeypatch):
    from app.services import images

    arm_real_ladder(monkeypatch)
    render = FakeRender(Exception(SAFETY_MSG), Exception(SAFETY_MSG),
                        ellipse_png(size=(1536, 1024)))
    monkeypatch.setattr(images, "_render", render)

    assert await images.generate_hero(hero_creature(id=4444)) == "/media/creatures/4444.webp"
    assert [c["quality"] for c in render.calls] == ["high", "high", "medium"]
    assert "A close cousin" in render.prompts[2]
    assert "night" not in render.prompts[2].lower()


async def test_hero_quality_knob_from_env(client, monkeypatch):
    from app import config
    from app.services import images

    monkeypatch.setenv("CHIMERA_HERO_QUALITY", "medium")
    config.get_settings.cache_clear()
    arm_real_ladder(monkeypatch)
    render = FakeRender(ellipse_png(size=(1536, 1024)))
    monkeypatch.setattr(images, "_render", render)

    assert images.hero_ladder() == ("medium", "medium", "medium", "medium")
    assert await images.generate_hero(hero_creature(id=4343)) == "/media/creatures/4343.webp"
    assert render.calls[0]["quality"] == "medium"


# -- boot resweep ---------------------------------------------------------------

async def test_resweep_heals_stuck_parts_and_tightens_media_once(client, monkeypatch):
    from app.config import get_settings
    from app.db import session_factory
    from app.models import CustomPart, ImageStatus
    from app.services import ai, images
    from app.services import library as lib
    from app.services import summon as summon_svc

    parts_dir = get_settings().media_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    padded = ellipse_png(box=(100, 200, 400, 700))  # 1024 square, creature off-centre
    (parts_dir / "custom_leaf-fox.png").write_bytes(padded)

    async with session_factory()() as db:
        stuck = CustomPart(slug="custom/charizard", name="Charizard", category="mythic",
                           portrait_description="An orange fire lizard with teal wings.",
                           portrait_status=ImageStatus.failed, art=None)
        fine = CustomPart(slug="custom/leaf-fox", name="Leaf Fox", category="living",
                          portrait_description="A tan fox with leaf-shaped ears.",
                          portrait_status=ImageStatus.complete,
                          art="/media/parts/custom_leaf-fox.png")
        db.add_all([stuck, fine])
        await db.commit()
        for row in (stuck, fine):
            summon_svc.register(row)

    monkeypatch.setattr(ai, "ai_enabled", lambda: True)
    calls: list[tuple] = []

    async def fake_portrait(file_slug, name, description, *, names=None):
        calls.append((file_slug, name, names))
        (parts_dir / f"{file_slug}.webp").write_bytes(b"webp")
        return f"/media/parts/{file_slug}.webp"

    monkeypatch.setattr(images, "generate_part_portrait", fake_portrait)

    await summon_svc.resweep_portraits()

    # Only the stranded part re-rendered, with its own name on the scrub list.
    assert calls == [("custom_charizard", "Charizard", ["Charizard"])]
    async with session_factory()() as db:
        rows = {r.slug: r for r in (await db.execute(select(CustomPart))).scalars()}
    assert rows["custom/charizard"].art == "/media/parts/custom_charizard.webp"
    assert rows["custom/charizard"].portrait_status is ImageStatus.complete
    assert rows["custom/leaf-fox"].art == "/media/parts/custom_leaf-fox.png"
    healed = lib.source_by_slug("custom/charizard")
    assert healed.art == "/media/parts/custom_charizard.webp"
    assert healed.portrait_status == "complete"

    # The tight pass ran once, in place, format preserved.
    assert (parts_dir / ".tight-v1").exists()
    with Image.open(parts_dir / "custom_leaf-fox.png") as img:
        assert img.format == "PNG"
        assert img.size == alpha_bbox_size(padded)

    # Second boot: nothing to render, nothing to tighten.
    stamp = (parts_dir / "custom_leaf-fox.png").stat().st_mtime_ns
    await summon_svc.resweep_portraits()
    assert len(calls) == 1
    assert (parts_dir / "custom_leaf-fox.png").stat().st_mtime_ns == stamp


async def test_resweep_is_a_no_op_without_ai(client):
    from app.db import session_factory
    from app.models import CustomPart, ImageStatus
    from app.services import summon as summon_svc

    async with session_factory()() as db:
        db.add(CustomPart(slug="custom/eevee", name="Eevee", portrait_status=ImageStatus.failed))
        await db.commit()
    await summon_svc.resweep_portraits()  # stub mode: never raises, never renders
    async with session_factory()() as db:
        row = (await db.execute(select(CustomPart))).scalars().one()
        assert row.portrait_status is ImageStatus.failed and row.art is None


# -- retry endpoint + library payload -------------------------------------------

async def test_retry_portrait_endpoint_states(client, monkeypatch):
    from app.db import session_factory
    from app.models import CustomPart, ImageStatus
    from app.services import summon as summon_svc

    assert (await client.post("/api/library/custom/nope/retry-portrait")).status_code == 404

    async with session_factory()() as db:
        db.add_all([
            CustomPart(slug="custom/charizard", name="Charizard",
                       portrait_status=ImageStatus.failed),
            CustomPart(slug="custom/leaf-fox", name="Leaf Fox",
                       portrait_status=ImageStatus.complete,
                       art="/media/parts/custom_leaf-fox.webp"),
            CustomPart(slug="custom/zapdos", name="Zapdos", portrait_status=ImageStatus.pending),
        ])
        await db.commit()

    # Stub mode: nothing to spend with — a friendly 409, not a silent no-op.
    res = await client.post("/api/library/custom/charizard/retry-portrait")
    assert res.status_code == 409 and "offline" in res.json()["detail"]

    # Art already there: say so without spending (both slug forms).
    for slug in ("leaf-fox", "custom/leaf-fox"):
        res = await client.post(f"/api/library/custom/{slug}/retry-portrait")
        assert res.status_code == 200, res.text
        assert res.json() == {"slug": "custom/leaf-fox", "portrait_status": "complete"}

    # Mid-render: report it, never double-queue.
    async def explode(db, slug):
        raise AssertionError("retry_portrait called for a part that is already rendering")

    monkeypatch.setattr(summon_svc, "retry_portrait", explode)
    res = await client.post("/api/library/custom/zapdos/retry-portrait")
    assert res.status_code == 200
    assert res.json() == {"slug": "custom/zapdos", "portrait_status": "rendering"}


async def test_retry_portrait_requeues_a_failed_part(client, monkeypatch):
    from app.db import session_factory
    from app.models import CustomPart, ImageStatus
    from app.services import ai
    from app.services import library as lib
    from app.services import summon as summon_svc

    async with session_factory()() as db:
        row = CustomPart(slug="custom/charizard", name="Charizard",
                         portrait_status=ImageStatus.failed)
        db.add(row)
        await db.commit()
        summon_svc.register(row)

    monkeypatch.setattr(ai, "ai_enabled", lambda: True)
    rendered: list[int] = []

    async def fake_task(part_id):
        rendered.append(part_id)

    monkeypatch.setattr(summon_svc, "_portrait_task", fake_task)

    res = await client.post("/api/library/custom/custom/charizard/retry-portrait")
    assert res.status_code == 200, res.text
    assert res.json() == {"slug": "custom/charizard", "portrait_status": "rendering"}
    await asyncio.sleep(0)  # let the spawned task take its first step
    assert rendered == [row.id]
    async with session_factory()() as db:
        assert (await db.get(CustomPart, row.id)).portrait_status is ImageStatus.pending
    assert lib.source_by_slug("custom/charizard").portrait_status == "pending"
    body = (await client.get("/api/library")).json()
    part = next(s for s in body["sources"] if s["slug"] == "custom/charizard")
    assert part["portrait_status"] == "pending"


async def test_library_exposes_portrait_status(client, tmp_path):
    author_library(tmp_path)
    await client.post("/api/library/summon", json={"query": "quokka"})  # stub: no render
    body = (await client.get("/api/library")).json()
    by_slug = {s["slug"]: s for s in body["sources"]}
    assert by_slug["dragon"]["portrait_status"] == "complete"
    assert by_slug["custom/quokka"]["custom"] is True
    assert by_slug["custom/quokka"]["portrait_status"] == "failed"
