#!/usr/bin/env python3
"""QA screenshot sweep + mock side-by-sides + type-scale audit.

Usage (backend on :8040, vite on :5187 — or pass --base):
    .venv/bin/python scripts/qa_screens.py [--out qa/uxpass] [--base http://localhost:5187]

Captures every screen at iPad-landscape (1180x820) and desktop (1440x900),
records console errors to console.json, walks the DOM for computed font sizes
(minimum per screen + every offender below the 13px floor -> fonts.json), and
composes side-by-side JPEGs against the art-direction mocks where one exists.

Stubbed-by-route-interception (backend contract still being built in
parallel; marked in the report):
  * GET /api/tournaments/current  — arena landing (derived from the real
    tournament list so the bracket shown is real data)
  * the three FROZEN Fusion Wait states (fw_a/fw_b/fw_c) via the creature
    detail endpoint — no real generation, no API spend
Interaction shots: codex_release (RELEASE confirm), battle_scout (fighter
stat modal). DELETE endpoints are never called by the sweep.
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

# route -> (hash path, settle ms). Bracket/battle/finale routes are derived
# from the live tournament list at runtime (see build_screens); the reveal
# needs an existing complete creature.
BASE_SCREENS = {
    "home": ("#/", 1400),
    "lab": ("#/lab", 1600),
    "codex": ("#/codex", 1600),
    "arena": ("#/arena", 1800),        # landing: current bracket (stubbed contract)
    "arena_setup": ("#/arena", 1800),  # landing: no current -> setup (stubbed null)
    "hall": ("#/hall", 1600),
}


def build_screens(base: str) -> dict[str, tuple[str, int]]:
    """Derive real ids for reveal/bracket/battle/finale from the scratch DB."""
    screens = dict(BASE_SCREENS)

    rows = fetch_json(base, "/api/creatures?sort=newest") or []
    done = next((c for c in rows if c.get("image_status") == "complete"), None)
    if done:
        screens["reveal"] = (f"#/reveal/{done['id']}", 2000)

    tours = fetch_json(base, "/api/tournaments") or []
    completed = [t for t in tours if t.get("status") == "complete"]
    board = completed[0] if completed else (tours[0] if tours else None)
    if board:
        screens["bracket"] = (f"#/arena/{board['id']}", 1600)
        matches = [m for r in board.get("rounds", []) for m in r.get("matches", [])]
        finals = board["rounds"][-1]["matches"] if board.get("rounds") else []
        final_ids = {m.get("id") for m in finals}
        # A resolved NON-final: the result view replays from cache, no AI call,
        # and no finale overlay covering the story card.
        fought = next(
            (m for m in matches if m.get("winner") is not None and m["id"] not in final_ids),
            None,
        )
        if fought:
            screens["battle"] = (f"#/arena/{board['id']}/{fought['id']}", 4600)
        # The championship match of an art-bearing tournament -> the Finale
        # overlay opens itself with the key art as the hero moment.
        arty = next(
            (t for t in completed
             if isinstance(t.get("final_art"), str) and t["final_art"].startswith("/")),
            None,
        )
        if arty:
            fid = arty["rounds"][-1]["matches"][0]["id"]
            screens["finale"] = (f"#/arena/{arty['id']}/{fid}", 6000)
    return screens

# ── Fusion Wait frozen states (stubbed via route interception) ──────────────
# Distinct fake ids so each state mounts a fresh Reveal (App keys screens by
# route id). The library still hits the real backend — read-only.

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

# The DOM-walk that finds the smallest rendered font on a screen and every
# visible text element below the 13px floor.
FONT_AUDIT_JS = """
() => {
  let min = Infinity;
  const below = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (!node.textContent || !node.textContent.trim()) continue;
    const el = node.parentElement;
    if (!el || seen.has(el)) continue;
    seen.add(el);
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    if (parseFloat(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (r.bottom < 0 || r.top > innerHeight) continue;
    const fs = parseFloat(cs.fontSize);
    if (!fs) continue;
    if (fs < min) min = fs;
    if (fs < 13) {
      below.push({
        px: Math.round(fs * 10) / 10,
        text: node.textContent.trim().slice(0, 48),
        cls: String(el.className).slice(0, 60),
      });
    }
  }
  return { min: isFinite(min) ? Math.round(min * 10) / 10 : null,
           below: below.slice(0, 24) };
}
"""


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
    hero_path = (hero or {}).get("hero_image_path") or "/assets/parts/dragon.webp"
    thumb_path = (hero or {}).get("thumb_path") or hero_path
    base.update(image_status="complete", image_started=False,
                hero_image_path=hero_path, thumb_path=thumb_path)
    return base


def fetch_json(base: str, path: str):
    try:
        with urllib.request.urlopen(f"{base}{path}", timeout=5) as r:
            return json.load(r)
    except Exception:
        return None


def newest_hero(base: str) -> dict | None:
    """A real finished render for the fw_c stub, read from the live codex."""
    rows = fetch_json(base, "/api/creatures?sort=newest") or []
    for row in rows:
        if row.get("image_status") == "complete" and row.get("hero_image_path"):
            return row
    return None


def current_payload(base: str) -> str | None:
    """Build GET /api/tournaments/current from the REAL tournament list —
    the contract is stubbed, the bracket data is not."""
    rows = fetch_json(base, "/api/tournaments") or []
    active = next((t for t in rows if t.get("status") != "complete"), None)
    t = active or (rows[0] if rows else None)
    if not t:
        return None
    next_id = None
    for rnd in t.get("rounds", []):
        for m in rnd.get("matches", []):
            if m.get("winner") is None and m.get("a") and m.get("b"):
                next_id = m.get("id")
                break
        if next_id:
            break
    return json.dumps({"tournament": t, "next_match_id": next_id})


def main(base: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    errors: dict[str, list[str]] = {}
    fonts: dict[str, dict] = {}
    stubbed = ["tournaments/current (arena, arena_setup)", "fw_a", "fw_b", "fw_c"]

    current_body = current_payload(base)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for vp_name, (w, h) in VIEWPORTS.items():
            ctx = browser.new_context(viewport={"width": w, "height": h},
                                      device_scale_factor=2)
            page = ctx.new_page()
            key = [""]
            page.on("console", lambda m: errors.setdefault(key[0], []).append(m.text)
                    if m.type == "error" else None)

            def shot(name: str, route: str, settle: int, actions=None) -> None:
                key[0] = f"{name}:{vp_name}"
                page.goto(f"{base}/{route}")
                page.wait_for_timeout(settle)
                if actions:
                    actions()
                page.screenshot(path=str(out / f"{name}_{vp_name}.png"))
                fonts[key[0]] = page.evaluate(FONT_AUDIT_JS)
                print(f"  shot {name}_{vp_name}  (min font {fonts[key[0]]['min']}px)")

            def stub_current(body: str | None):
                def handler(route, _request=None, body=body):
                    route.fulfill(status=200, content_type="application/json",
                                  body=body if body else "null")
                page.route("**/api/tournaments/current", handler)

            for name, (route, settle) in SCREENS.items():
                if name == "arena":
                    stub_current(current_body)
                elif name == "arena_setup":
                    stub_current(None)
                shot(name, route, settle)
                if name in ("arena", "arena_setup"):
                    page.unroute("**/api/tournaments/current")

            # Interaction shots — the new tap-to-read/confirm surfaces.
            def open_release():
                try:
                    page.click(".release__quiet", timeout=3000)
                    page.wait_for_timeout(450)
                except Exception:
                    print("  (codex_release: no RELEASE button found)")

            shot("codex_release", SCREENS["codex"][0], SCREENS["codex"][1], open_release)

            def open_scout():
                try:
                    page.click(".corner--left .corner__id", timeout=3000)
                    page.wait_for_timeout(1400)
                except Exception:
                    print("  (battle_scout: fighter chip not clickable)")

            shot("battle_scout", SCREENS["battle"][0], SCREENS["battle"][1], open_scout)

            # Fusion Wait frozen states — detail endpoint stubbed, zero AI spend.
            hero = newest_hero(base)
            for state, (cid, settle) in FW_STATES.items():
                body = json.dumps(fw_payload(state, cid, hero))
                pattern = f"**/api/creatures/{cid}"

                def stub(route, _request=None, body=body):
                    route.fulfill(status=200, content_type="application/json", body=body)

                page.route(pattern, stub)
                shot(f"fw_{state}", f"#/reveal/{cid}", settle)
                page.unroute(pattern)
            ctx.close()
        browser.close()

    (out / "console.json").write_text(json.dumps(errors, indent=2))
    (out / "fonts.json").write_text(json.dumps(fonts, indent=2))
    (out / "stubbed.json").write_text(json.dumps(stubbed, indent=2))

    bad = {k: v for k, v in errors.items() if v}
    print(f"\nconsole errors on {len(bad)} screen(s)" + (f": {list(bad)}" if bad else ""))

    print("\nmin font per screen (floor is 13px):")
    worst = []
    for k in sorted(fonts):
        f = fonts[k]
        flag = "  <-- BELOW FLOOR" if (f["min"] or 99) < 13 else ""
        print(f"  {k:28s} {f['min']}px{flag}")
        if f["below"]:
            worst.append((k, f["below"][:3]))
    for k, items in worst:
        print(f"  offenders on {k}: {items}")

    for name, mock_file in MOCKS.items():
        shot_p = out / f"{name}_ipad.png"
        mock_p = ROOT / "art-direction" / mock_file
        if not (shot_p.exists() and mock_p.exists()):
            continue
        shot_img = Image.open(shot_p).convert("RGB")
        mock = Image.open(mock_p).convert("RGB")
        target_h = 800
        shot_img = shot_img.resize((int(shot_img.width * target_h / shot_img.height), target_h))
        mock = mock.resize((int(mock.width * target_h / mock.height), target_h))
        sheet = Image.new("RGB", (mock.width + shot_img.width + 24, target_h + 48), (10, 10, 14))
        sheet.paste(mock, (0, 40))
        sheet.paste(shot_img, (mock.width + 24, 40))
        sheet.save(out / f"sxs_{name}.jpg", quality=82)
        print(f"  side-by-side sxs_{name}.jpg  (mock LEFT, ours RIGHT)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="qa/uxpass")
    ap.add_argument("--base", default="http://localhost:5187")
    a = ap.parse_args()
    main(a.base, Path(a.out))
