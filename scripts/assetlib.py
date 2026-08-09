"""Asset-generation pipeline for Chimera Creator.

All generation via OpenAI gpt-image-1.5 (native transparent backgrounds for
cutout assets — no chroma-key). Raw renders land in scripts/raw/ (gitignored)
so any asset can be re-cropped without re-spending; finished PNGs land in
frontend/public/assets/ at the sizes in docs/ASSET_WISHLIST.md.
"""

import base64
import io
import os
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "scripts" / "raw"
OUT_DIR = ROOT / "frontend" / "public" / "assets"
MODEL = "gpt-image-1.5"

STYLE = (
    "Cinematic sci-fi game art for a neon creature-laboratory interface aimed "
    "at kids 7-10. Deep navy and black environments, electric cyan and blue "
    "holographic light, violet-purple fusion energy as the signature accent, "
    "gold reserved for champions and trophies. Clean industrial sci-fi "
    "surfaces, glass and brushed dark metal, glowing circuit filigree, "
    "volumetric light. Epic and premium, never scary or gory. Absolutely no "
    "text, letters, numbers, watermarks, or UI widgets in the image. "
)

PORTRAIT_STYLE = (
    "Realistic AAA creature portrait for a neon sci-fi game, aimed at kids "
    "7-10. The creature keeps its NATURAL realistic coloring and detailed "
    "texture, lit dramatically with a subtle electric-cyan and violet rim "
    "light as if standing in a dark holographic lab. Epic, fierce, premium — "
    "never gory. Full body visible, three-quarter dramatic pose, centered, "
    "not touching image edges. Absolutely no text or watermarks. "
)

_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is None:
        env = ROOT / ".env"
        for line in env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)
        from openai import OpenAI

        _CLIENT = OpenAI(api_key=os.environ["OPEN_AI_API_KEY"], timeout=300)
    return _CLIENT


def generate(prompt, name, *, size="1024x1024", transparent=True,
             quality="high", references=(), retries=3):
    """Generate one image; save raw PNG to scripts/raw/<name>.png; return path."""
    raw_path = RAW_DIR / f"{name}.png"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    client = _client()
    kwargs = dict(model=MODEL, prompt=prompt, size=size, quality=quality,
                  output_format="png")
    if transparent:
        kwargs["background"] = "transparent"
    last = None
    for attempt in range(retries):
        t0 = time.time()
        try:
            if references:
                mime = {".png": "image/png", ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg", ".webp": "image/webp"}
                imgs = [(Path(r).name, io.BytesIO(Path(r).read_bytes()),
                         mime[Path(r).suffix.lower()])
                        for r in references]
                resp = client.images.edit(image=imgs, **kwargs)
            else:
                resp = client.images.generate(**kwargs)
            raw_path.write_bytes(base64.b64decode(resp.data[0].b64_json))
            print(f"  raw {name}: {time.time() - t0:.0f}s")
            return raw_path
        except Exception as e:  # noqa: BLE001 - retry transient API errors
            last = e
            wait = 2 ** (attempt + 1)
            print(f"  retry {name} in {wait}s: {str(e)[:120]}")
            time.sleep(wait)
    raise RuntimeError(f"generation failed for {name}: {last}")


# The shipped assets are WebP (q90/method 6 — ~90% smaller than PNG with alpha
# intact). The raw API output stays PNG in scripts/raw as the archival original.
WEBP = {"quality": 90, "method": 6}


def finalize(raw_path, slot, w, h, *, margin=0.04, trim=True, alpha_thresh=0):
    """Trim transparent borders, fit to WxH canvas, save to assets/<slot>.webp.

    alpha_thresh ignores near-transparent pixels when measuring the bounding
    box, so a wide faint glow halo cannot shrink the actual subject.
    """
    img = Image.open(raw_path).convert("RGBA")
    if trim:
        if alpha_thresh:
            mask = img.getchannel("A").point(
                lambda a: 255 if a > alpha_thresh else 0)
            bbox = mask.getbbox()
        else:
            bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
    scale = min((w * (1 - margin)) / img.width, (h * (1 - margin)) / img.height)
    img = img.resize((max(1, int(img.width * scale)),
                      max(1, int(img.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(img, ((w - img.width) // 2, (h - img.height) // 2), img)
    out = OUT_DIR / f"{slot}.webp"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "WEBP", **WEBP)
    return out


def finalize_opaque(raw_path, slot, w, h):
    """Cover-crop an opaque scene to WxH and save."""
    img = Image.open(raw_path).convert("RGB")
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    x = (img.width - w) // 2
    y = (img.height - h) // 2
    img = img.crop((x, y, x + w, y + h))
    out = OUT_DIR / f"{slot}.webp"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "WEBP", **WEBP)
    return out
