#!/usr/bin/env python3
"""Does gpt-image-2.5 still refuse a trademarked NAME, and does its new
`moderation="low"` change that? One named Charizard part prompt per setting.
Writes r25/safety_<model>_<moderation>.png on success."""
import base64, json, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from run_2_5 import OUT  # noqa: E402  (loads .env)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
from app.services.images import part_portrait_prompt, is_safety_rejection  # noqa: E402
from openai import OpenAI

DESC = ("Charizard: an orange bipedal dragon with a cream belly, teal inner wings, "
        "a long tail ending in a burning flame, two horns and a fierce grin.")
client = OpenAI(api_key=os.environ["OPEN_AI_API_KEY"], timeout=300)
for model in ("gpt-image-2.5-flare",):
    for moderation in ("auto", "low"):
        t0 = time.time()
        try:
            resp = client.images.generate(model=model, prompt=part_portrait_prompt("Charizard", DESC),
                                          size="1024x1024", quality="medium", background="transparent",
                                          output_format="png", moderation=moderation)
            png = base64.b64decode(resp.data[0].b64_json)
            (OUT / f"safety_{model}_{moderation}.png").write_bytes(png)
            print(json.dumps({"model": model, "moderation": moderation, "ok": True,
                              "latency_s": round(time.time() - t0, 1), "bytes": len(png)}))
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"model": model, "moderation": moderation, "ok": False,
                              "safety": is_safety_rejection(exc), "error": str(exc)[:220]}))
