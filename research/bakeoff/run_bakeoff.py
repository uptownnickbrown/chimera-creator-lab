#!/usr/bin/env python3
"""Image-model bakeoff: 3 chimera specs x 4 contenders.

OpenAI models use native background=transparent; Gemini models use magenta
chroma + border-connected flood-fill removal (Agora technique). Outputs:
  raw/<spec>__<model>.png      raw model output
  cutout/<spec>__<model>.png   transparent-background cutout
  results.json                 latency + alpha stats per run
"""

import base64
import concurrent.futures as cf
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from specs import CHROMA, SPECS, STYLE

ROOT = HERE.parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)

RAW = HERE / "raw"
CUT = HERE / "cutout"
RAW.mkdir(exist_ok=True)
CUT.mkdir(exist_ok=True)

OPENAI_MODELS = ["gpt-image-2", "gpt-image-1.5"]
GEMINI_MODELS = ["gemini-3-pro-image", "gemini-3.1-flash-image"]


def gen_openai(model: str, spec_key: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPEN_AI_API_KEY"], timeout=300)
    prompt = STYLE + " " + SPECS[spec_key]["prompt"] + " Transparent background."
    t0 = time.time()
    resp = client.images.generate(
        model=model,
        prompt=prompt,
        size="1536x1024",
        quality="high",
        background="transparent",
        output_format="png",
    )
    dt = time.time() - t0
    img_bytes = base64.b64decode(resp.data[0].b64_json)
    name = f"{spec_key}__{model.replace('.', '_')}"
    (RAW / f"{name}.png").write_bytes(img_bytes)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    img.save(CUT / f"{name}.png")  # native transparency: raw == cutout
    return {"model": model, "spec": spec_key, "latency_s": round(dt, 1),
            "native_alpha": True, **alpha_stats(img)}


def gen_gemini(model: str, spec_key: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = STYLE + " " + SPECS[spec_key]["prompt"] + CHROMA
    cfg = types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="3:2", image_size="2K"),
    )
    t0 = time.time()
    resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
    dt = time.time() - t0
    img = None
    for part in resp.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
    if img is None:
        raise RuntimeError(f"no image part from {model} for {spec_key}")
    name = f"{spec_key}__{model.replace('.', '_')}"
    img.save(RAW / f"{name}.png")
    cut = chroma_cutout(img)
    cut.save(CUT / f"{name}.png")
    return {"model": model, "spec": spec_key, "latency_s": round(dt, 1),
            "native_alpha": False, **alpha_stats(cut)}


def chroma_cutout(img: Image.Image, tol: int = 130) -> Image.Image:
    """Remove border-connected magenta background (Agora flood-fill technique)."""
    arr = np.array(img.convert("RGB"), dtype=np.int16)
    dist = np.sqrt(((arr - np.array([255, 0, 255])) ** 2).sum(axis=2))
    near = dist < tol
    # keep only background regions connected to the image border
    labels, _ = ndimage.label(near)
    border_labels = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    border_labels.discard(0)
    bg = np.isin(labels, list(border_labels))
    # soften edge: shrink bg by 1px then feather alpha at boundary
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    alpha = ndimage.minimum_filter(alpha, size=2)
    out = np.dstack([np.array(img.convert("RGB"), dtype=np.uint8), alpha])
    return Image.fromarray(out, "RGBA")


def alpha_stats(img: Image.Image) -> dict:
    a = np.array(img.split()[-1])
    opaque = (a > 200).mean()
    partial = ((a > 10) & (a <= 200)).mean()
    return {"pct_opaque": round(float(opaque) * 100, 1),
            "pct_edge": round(float(partial) * 100, 2),
            "size": list(img.size)}


def main():
    jobs = []
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for spec in SPECS:
            for m in OPENAI_MODELS:
                jobs.append(ex.submit(gen_openai, m, spec))
            for m in GEMINI_MODELS:
                jobs.append(ex.submit(gen_gemini, m, spec))
        results = []
        for fut in cf.as_completed(jobs):
            try:
                r = fut.result()
                print(f"OK  {r['spec']:<12} {r['model']:<28} {r['latency_s']:>6}s "
                      f"opaque={r['pct_opaque']}%")
            except Exception as e:
                r = {"error": f"{type(e).__name__}: {e}"}
                print(f"ERR {r['error'][:160]}")
            results.append(r)
    (HERE / "results.json").write_text(json.dumps(results, indent=2))
    print(f"\n{len([r for r in results if 'error' not in r])}/{len(results)} succeeded")


if __name__ == "__main__":
    main()
