#!/usr/bin/env python3
"""Finals key art (images.edit, two hero cutouts) on gpt-image-2.5 — the
runtime prompt verbatim. Writes r25/keyart_<model>_<quality>.png + json."""
import base64, io, json, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from run_2_5 import OUT, PRICE  # noqa: E402
from openai import OpenAI

PROMPT = (
    "Epic cinematic championship key art for a AAA monster game, child-"
    "friendly (no gore, no blood). The FIRST attached creature and the "
    "SECOND attached creature clash mid-battle in a futuristic holographic "
    "grand arena at night — gold championship light beams, violet and "
    "cyan energy, sparks and spray flying, both titans rearing at each "
    "other in a perfectly balanced duel, neither winning. Keep BOTH "
    "creatures' designs EXACTLY as shown in the attached images — same "
    "anatomy, colors, plates, proportions. No text or watermarks."
)
A = OUT / "stormback__gpt-image-2.5-flare__high.png"
B = OUT / "basilodion__gpt-image-2.5-flare__high.png"
client = OpenAI(api_key=os.environ["OPEN_AI_API_KEY"], timeout=300)
out = []
for model, quality in (("gpt-image-2.5-flare", "high"), ("gpt-image-2.5-sunburst", "high"), ("gpt-image-2.5-flare", "xhigh")):
    t0 = time.time()
    try:
        resp = client.images.edit(model=model,
                                  image=[("a.png", io.BytesIO(A.read_bytes()), "image/png"),
                                         ("b.png", io.BytesIO(B.read_bytes()), "image/png")],
                                  prompt=PROMPT, size="1536x1024", quality=quality, output_format="png")
        png = base64.b64decode(resp.data[0].b64_json)
        (OUT / f"keyart_{model}_{quality}.png").write_bytes(png)
        u = resp.usage
        d = u.input_tokens_details
        cost = (getattr(d, "text_tokens", 0) or 0) * 5 / 1e6 + (getattr(d, "image_tokens", 0) or 0) * 8 / 1e6 + u.output_tokens * PRICE[model]["img_out"] / 1e6
        r = {"model": model, "quality": quality, "latency_s": round(time.time() - t0, 1),
             "in_tok": u.input_tokens, "out_tok": u.output_tokens, "cost_usd": round(cost, 4)}
    except Exception as exc:  # noqa: BLE001
        r = {"model": model, "quality": quality, "error": str(exc)[:200]}
    out.append(r); print(json.dumps(r), flush=True)
(OUT / "results_keyart.json").write_text(json.dumps(out, indent=2))
