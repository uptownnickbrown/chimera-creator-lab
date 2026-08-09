#!/usr/bin/env python3
"""QA screenshot sweep + mock side-by-sides for the acceptance loop.

Usage (backend on :8000, vite on :5173 — or pass --base):
    .venv/bin/python scripts/qa_screens.py [--out qa/shots] [--base http://localhost:5173]

Captures every screen at iPad-landscape (1180x820) and desktop (1440x900),
records console errors to console.json, and composes side-by-side JPEGs
against the art-direction mocks where one exists.

Also sweeps the generation-time Fusion Wait in three FROZEN states (fw_a/
fw_b/fw_c) by stubbing the creature detail endpoint with Playwright route
interception — no real generation, no API spend, runs in every sweep.
"""
import argparse
import json
import urllib.request
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

# ── Fusion Wait frozen states (stubbed via route interception) ──────────────
# Distinct fake ids so each state mounts a fresh Reveal (App keys screens by
# route id). The carousel/library still hit the real backend — read-only.

FW_SOURCES = ["dragon", "stegosaurus", "electric-eel", "great-white-shark"]
FW_STATS = {"power": 88, "speed": 64, "armor": 79, "size": 71,
            "special_name": "Electricity", "special": 93}
FW_ABILITIES = [
    {"name": "Thunder Bite", "sources": ["Great White Shark", "Electric Eel"],
     "blurb": "Clamps down with a jolt of crackling lightning that will not let go!"},
    {"name": "Ember Plate Wall", "sources": ["Dragon", "Stegosaurus"],
     "blurb": "Raises glowing armored plates to block the next big attack!"},
    {"name": "Storm Surge", "sources": ["Dragon", "Electric Eel"],
     "blurb": "Unleashes a huge burst of energy that knocks enemies backward!"},
]
# state -> (fake id, settle ms)
FW_STATES = {"a": (99991, 2600), "b": (99992, 5200), "c": (99993, 4200)}


def fw_payload(state: str, cid: int, hero: dict | None) -> dict:
    """A complete, frozen CreatureDetail for one Fusion Wait state."""
    base = {
        "id": cid, "name": "", "title": "", "rarity": "", "role": "",
        "sources": FW_SOURCES, "core_stats": {},
        "record_status": "generating", "image_status": "pending",
        "ability_names": [], "signature_ability": "", "image_started": False,
        "hero_image_path": None, "thumb_path": None, "favorite": False,
        "wins": 0, "losses": 0, "championships": 0, "created_at": None,
        "abilities": [], "strengths": [], "weaknesses": [],
        "environment_affinities": {}, "fun_fact": "", "anatomy_plan": "",
        "visual_spec": "", "records": {}, "win_rate": 0,
    }
    # (a) mid-weave: name + stats streamed, two ability names so far.
    base.update(name="Voltadon", core_stats=FW_STATS,
                ability_names=[a["name"] for a in FW_ABILITIES[:2]])
    if state == "a":
        return base
    # (b) painting: record complete, render honestly started -> walkthrough on.
    base.update(
        record_status="complete", image_started=True, ability_names=[],
        title="The Thundered Leviathan", rarity="Epic",
        role="Striker / Burst Damage", abilities=FW_ABILITIES,
        strengths=["Hits harder than almost anything its size",
                   "Its signature power turns fights around"],
        weaknesses=["Slow to turn once it commits to a charge",
                    "Thin plating on the belly - a solid hit really lands"],
        fun_fact="It can charge its plates with lightning while it swims.",
    )
    if state == "b":
        return base
    # (c) complete: hero ready -> the reveal detonates.
    hero_path = (hero or {}).get("hero_image_path") or "/assets/parts/dragon.png"
    thumb_path = (hero or {}).get("thumb_path") or hero_path
    base.update(image_status="complete", image_started=False,
                hero_image_path=hero_path, thumb_path=thumb_path)
    return base


def newest_hero(base: str) -> dict | None:
    """A real finished render for the fw_c stub, read from the live codex."""
    try:
        with urllib.request.urlopen(f"{base}/api/creatures?sort=newest", timeout=5) as r:
            rows = json.load(r)
        for row in rows:
            if row.get("image_status") == "complete" and row.get("hero_image_path"):
                return row
    except Exception:
        pass
    return None


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

            # Fusion Wait frozen states — detail endpoint stubbed, zero AI spend.
            hero = newest_hero(base)
            for state, (cid, settle) in FW_STATES.items():
                key[0] = f"fw_{state}:{vp_name}"
                body = json.dumps(fw_payload(state, cid, hero))
                pattern = f"**/api/creatures/{cid}"

                def stub(route, _request=None, body=body):
                    route.fulfill(status=200, content_type="application/json", body=body)

                page.route(pattern, stub)
                page.goto(f"{base}/#/reveal/{cid}")
                page.wait_for_timeout(settle)
                page.screenshot(path=str(out / f"fw_{state}_{vp_name}.png"))
                page.unroute(pattern)
                print(f"  shot fw_{state}_{vp_name}")
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
