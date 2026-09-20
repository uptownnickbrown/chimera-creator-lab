#!/usr/bin/env python3
"""GPT-Image-2.5 bakeoff (2026-09-20): Flare / Sunburst vs the shipped
gpt-image-1.5, on the app's OWN prompts — three hero specs (1536x1024) and
two summoned-part portraits (1024x1024), native transparent PNG.

Outputs r25/<spec>__<model>__<quality>.png, r25/results.json (latency,
usage tokens -> exact cost, alpha stats), r25/sheet_<spec>.jpg contact
sheets on a checkerboard so transparency quality is visible.
"""
from __future__ import annotations

import base64
import concurrent.futures as cf
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "backend"))
from specs import SPECS  # noqa: E402
from app.services.images import HERO_STYLE, part_portrait_prompt  # noqa: E402

for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)

OUT = HERE / "r25"
OUT.mkdir(exist_ok=True)

# $/1M tokens (developers.openai.com/api/docs/pricing, 2026-09-20)
PRICE = {
    "gpt-image-1.5": {"text_in": 5.0, "img_out": 32.0},
    "gpt-image-2.5-flare": {"text_in": 5.0, "img_out": 30.0},
    "gpt-image-2.5-sunburst": {"text_in": 5.0, "img_out": 30.0},
}
HERO_CONFIGS = [
    ("gpt-image-1.5", "high"), ("gpt-image-1.5", "medium"),
    ("gpt-image-2.5-flare", "high"), ("gpt-image-2.5-flare", "medium"), ("gpt-image-2.5-flare", "low"),
    ("gpt-image-2.5-sunburst", "high"), ("gpt-image-2.5-sunburst", "medium"),
]
PART_CONFIGS = [
    ("gpt-image-1.5", "medium"),
    ("gpt-image-2.5-flare", "medium"), ("gpt-image-2.5-flare", "low"),
    ("gpt-image-2.5-sunburst", "medium"),
]
PARTS = {
    "komodo": ("Komodo Dragon", "A huge Komodo dragon with armored grey-brown scales, a long forked "
               "tongue flicking out, thick clawed legs and a heavy muscular tail."),
    "falcon": ("Peregrine Falcon", "A peregrine falcon in a steep hunting dive, slate-blue back, barred "
               "white chest, black hooded head, yellow feet and beak, wings swept back."),
}

JOBS = [("hero", key, m, q) for key in SPECS for (m, q) in HERO_CONFIGS] + \
       [("part", key, m, q) for key in PARTS for (m, q) in PART_CONFIGS]


def alpha_stats(png: bytes) -> dict:
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    a = np.asarray(img)[:, :, 3]
    opaque = (a > 247).mean() * 100
    edge = ((a > 8) & (a <= 247)).mean() * 100
    return {"size": list(img.size), "pct_opaque": round(float(opaque), 1),
            "pct_edge": round(float(edge), 2), "native_alpha": bool((a < 8).any())}


def run(job):
    from openai import OpenAI
    kind, key, model, quality = job
    if kind == "hero":
        prompt = HERO_STYLE + SPECS[key]["prompt"]
        size = "1536x1024"
    else:
        name, desc = PARTS[key]
        prompt = part_portrait_prompt(name, desc)
        size = "1024x1024"
    client = OpenAI(api_key=os.environ["OPEN_AI_API_KEY"], timeout=300)
    t0 = time.time()
    try:
        resp = client.images.generate(model=model, prompt=prompt, size=size, quality=quality,
                                      background="transparent", output_format="png")
    except Exception as exc:  # noqa: BLE001
        return {"kind": kind, "spec": key, "model": model, "quality": quality,
                "error": str(exc)[:300]}
    dt = round(time.time() - t0, 1)
    png = base64.b64decode(resp.data[0].b64_json)
    name = f"{key}__{model}__{quality}"
    (OUT / f"{name}.png").write_bytes(png)
    u = getattr(resp, "usage", None)
    usage = {}
    if u is not None:
        usage = {"input_tokens": getattr(u, "input_tokens", None),
                 "output_tokens": getattr(u, "output_tokens", None)}
    cost = None
    if usage.get("output_tokens") is not None:
        p = PRICE[model]
        cost = round((usage["input_tokens"] or 0) * p["text_in"] / 1e6
                     + usage["output_tokens"] * p["img_out"] / 1e6, 4)
    return {"kind": kind, "spec": key, "model": model, "quality": quality, "latency_s": dt,
            "bytes": len(png), "usage": usage, "cost_usd": cost, **alpha_stats(png)}


def checker(w, h, cell=24):
    img = Image.new("RGB", (w, h), (200, 200, 200))
    d = ImageDraw.Draw(img)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if (x // cell + y // cell) % 2:
                d.rectangle([x, y, x + cell, y + cell], fill=(150, 150, 150))
    return img


def sheet(kind, key, rows, configs):
    tile_w = 420
    tiles = []
    for (m, q) in configs:
        r = next((x for x in rows if x["spec"] == key and x["model"] == m and x["quality"] == q), None)
        p = OUT / f"{key}__{m}__{q}.png"
        if not r or "error" in r or not p.exists():
            continue
        im = Image.open(p).convert("RGBA")
        scale = tile_w / im.width
        im = im.resize((tile_w, int(im.height * scale)), Image.LANCZOS)
        bg = checker(tile_w, im.height + 44)
        bg.paste(im, (0, 44), im)
        d = ImageDraw.Draw(bg)
        d.rectangle([0, 0, tile_w, 44], fill=(20, 20, 30))
        d.text((8, 4), f"{m} / {q}", fill=(255, 255, 255))
        d.text((8, 22), f"{r['latency_s']}s  ${r['cost_usd']}  {r['usage'].get('output_tokens')} out-tok  "
                        f"edge {r['pct_edge']}%", fill=(180, 220, 255))
        tiles.append(bg)
    if not tiles:
        return
    cols = 4 if kind == "hero" else 4
    rows_n = (len(tiles) + cols - 1) // cols
    th = max(t.height for t in tiles)
    out = Image.new("RGB", (cols * (tile_w + 8), rows_n * (th + 8)), (10, 10, 14))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * (tile_w + 8), (i // cols) * (th + 8)))
    out.save(OUT / f"sheet_{key}.jpg", quality=86)


def main():
    results = []
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(run, JOBS):
            results.append(r)
            print(json.dumps({k: v for k, v in r.items() if k != "usage"}), flush=True)
    (OUT / "results.json").write_text(json.dumps(results, indent=2))
    for key in SPECS:
        sheet("hero", key, results, HERO_CONFIGS)
    for key in PARTS:
        sheet("part", key, results, PART_CONFIGS)
    print("done", len(results))


if __name__ == "__main__":
    main()
