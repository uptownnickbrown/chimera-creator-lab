#!/usr/bin/env python3
"""gpt-image-2 lacks native transparency; rerun it with chroma-key magenta."""
import base64, concurrent.futures as cf, io, json, os, sys, time
from pathlib import Path
from PIL import Image

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from specs import CHROMA, SPECS, STYLE
from run_bakeoff import RAW, CUT, chroma_cutout, alpha_stats

def gen(spec_key):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPEN_AI_API_KEY"], timeout=300)
    prompt = STYLE + " " + SPECS[spec_key]["prompt"] + CHROMA
    t0 = time.time()
    resp = client.images.generate(model="gpt-image-2", prompt=prompt,
                                  size="1536x1024", quality="high", output_format="png")
    dt = time.time() - t0
    img = Image.open(io.BytesIO(base64.b64decode(resp.data[0].b64_json))).convert("RGB")
    name = f"{spec_key}__gpt-image-2"
    img.save(RAW / f"{name}.png")
    cut = chroma_cutout(img)
    cut.save(CUT / f"{name}.png")
    return {"model": "gpt-image-2(chroma)", "spec": spec_key, "latency_s": round(dt, 1),
            "native_alpha": False, **alpha_stats(cut)}

results = json.loads((HERE / "results.json").read_text())
results = [r for r in results if "error" not in r]
with cf.ThreadPoolExecutor(max_workers=3) as ex:
    for fut in cf.as_completed([ex.submit(gen, s) for s in SPECS]):
        try:
            r = fut.result(); results.append(r)
            print(f"OK  {r['spec']:<12} {r['model']:<24} {r['latency_s']:>6}s opaque={r['pct_opaque']}%")
        except Exception as e:
            print(f"ERR {type(e).__name__}: {str(e)[:160]}")
(HERE / "results.json").write_text(json.dumps(results, indent=2))
