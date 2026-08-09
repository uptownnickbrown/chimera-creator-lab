#!/usr/bin/env python3
"""QA screenshot sweep + mock side-by-sides for the acceptance loop.

Usage (backend on :8000, vite on :5173 — or pass --base):
    .venv/bin/python scripts/qa_screens.py [--out qa/shots] [--base http://localhost:5173]

Captures every screen at iPad-landscape (1180x820) and desktop (1440x900),
records console errors to console.json, and composes side-by-side JPEGs
against the art-direction mocks where one exists.
"""
import argparse
import json
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
MOCKS = {
    "home": "welcome.png",
    "lab": "build.png",
    "reveal": "created.png",
    "codex": "codex.png",
    "battle": "battle.png",
}
VIEWPORTS = {"ipad": (1180, 820), "desktop": (1440, 900)}

# route -> (hash path, settle ms). Reveal needs an existing complete creature.
SCREENS = {
    "home": ("#/", 1400),
    "lab": ("#/lab", 1600),
    "codex": ("#/codex", 1400),
    "reveal": ("#/reveal/1", 2000),
    "arena": ("#/arena", 1400),
    "bracket": ("#/arena/1", 1400),
    # An already-resolved match: the result view replays from cache, no AI call.
    "battle": ("#/arena/1/r0m1", 4200),
    "hall": ("#/hall", 1400),
}


def main(base: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    errors: dict[str, list[str]] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for vp_name, (w, h) in VIEWPORTS.items():
            ctx = browser.new_context(viewport={"width": w, "height": h},
                                      device_scale_factor=2)
            page = ctx.new_page()
            key = [""]
            page.on("console", lambda m: errors.setdefault(key[0], []).append(m.text)
                    if m.type == "error" else None)
            for name, (route, settle) in SCREENS.items():
                key[0] = f"{name}:{vp_name}"
                page.goto(f"{base}/{route}")
                page.wait_for_timeout(settle)
                page.screenshot(path=str(out / f"{name}_{vp_name}.png"))
                print(f"  shot {name}_{vp_name}")
            ctx.close()
        browser.close()

    (out / "console.json").write_text(json.dumps(errors, indent=2))
    bad = {k: v for k, v in errors.items() if v}
    print(f"console errors on {len(bad)} screen(s)" + (f": {list(bad)}" if bad else ""))

    for name, mock_file in MOCKS.items():
        shot_p = out / f"{name}_ipad.png"
        mock_p = ROOT / "art-direction" / mock_file
        if not (shot_p.exists() and mock_p.exists()):
            continue
        shot = Image.open(shot_p).convert("RGB")
        mock = Image.open(mock_p).convert("RGB")
        target_h = 800
        shot = shot.resize((int(shot.width * target_h / shot.height), target_h))
        mock = mock.resize((int(mock.width * target_h / mock.height), target_h))
        sheet = Image.new("RGB", (mock.width + shot.width + 24, target_h + 48), (10, 10, 14))
        sheet.paste(mock, (0, 40))
        sheet.paste(shot, (mock.width + 24, 40))
        sheet.save(out / f"sxs_{name}.jpg", quality=82)
        print(f"  side-by-side sxs_{name}.jpg  (mock LEFT, ours RIGHT)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="qa/shots")
    ap.add_argument("--base", default="http://localhost:5173")
    a = ap.parse_args()
    main(a.base, Path(a.out))
