#!/usr/bin/env python3
"""Follow-up probe: the 2.5 `xhigh` tier on the three hero specs (a tier
gpt-image-1.5 never had). Writes r25/results_xhigh.json alongside run_2_5."""
import concurrent.futures as cf, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from run_2_5 import OUT, SPECS, run  # noqa: E402

JOBS = [("hero", key, m, "xhigh") for key in SPECS for m in ("gpt-image-2.5-flare", "gpt-image-2.5-sunburst")]
with cf.ThreadPoolExecutor(max_workers=3) as ex:
    results = list(ex.map(run, JOBS))
for r in results:
    print(json.dumps({k: v for k, v in r.items() if k != "usage"}), flush=True)
(OUT / "results_xhigh.json").write_text(json.dumps(results, indent=2))
