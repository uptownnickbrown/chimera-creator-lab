#!/usr/bin/env python3
"""(a) gpt-image-1.5 medium-quality latency/quality; (b) identity-preserving
battle key art via images.edit with two hero cutouts as reference input."""
import base64, concurrent.futures as cf, io, os, sys, time
from pathlib import Path
from PIL import Image

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from specs import SPECS, STYLE
from run_bakeoff import CUT

def client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["OPEN_AI_API_KEY"], timeout=300)

def medium(spec_key):
    prompt = STYLE + " " + SPECS[spec_key]["prompt"] + " Transparent background."
    t0 = time.time()
    r = client().images.generate(model="gpt-image-1.5", prompt=prompt,
        size="1536x1024", quality="medium", background="transparent", output_format="png")
    dt = time.time() - t0
    p = HERE / "review" / f"medium_{spec_key}.png"
    p.write_bytes(base64.b64decode(r.data[0].b64_json))
    return f"medium {spec_key}: {dt:.1f}s"

def keyart():
    a = (CUT / "stormback__gpt-image-1_5.png").read_bytes()
    b = (CUT / "basilodion__gpt-image-1_5.png").read_bytes()
    prompt = (
        "Epic cinematic battle key art for a AAA monster game, child-friendly (no gore). "
        "The FIRST attached creature and the SECOND attached creature face off mid-battle "
        "on a storm-lashed rocky coast at night: crashing waves, forked lightning, rain. "
        "Keep BOTH creatures' designs EXACTLY as shown in the attached images — same "
        "anatomy, colors, plates, claws, proportions. First creature on the left lunging, "
        "second on the right rearing up with pincers raised. Dramatic rim lighting, "
        "spray and sparks flying. No text or watermarks.")
    t0 = time.time()
    r = client().images.edit(model="gpt-image-1.5",
        image=[("stormback.png", io.BytesIO(a), "image/png"),
               ("basilodion.png", io.BytesIO(b), "image/png")],
        prompt=prompt, size="1536x1024", quality="high")
    dt = time.time() - t0
    (HERE / "review" / "keyart_finals.png").write_bytes(base64.b64decode(r.data[0].b64_json))
    return f"keyart: {dt:.1f}s"

with cf.ThreadPoolExecutor(max_workers=3) as ex:
    futs = [ex.submit(medium, "stormback"), ex.submit(medium, "tideburn"), ex.submit(keyart)]
    for f in cf.as_completed(futs):
        try: print(f.result())
        except Exception as e: print("ERR", type(e).__name__, str(e)[:300])
