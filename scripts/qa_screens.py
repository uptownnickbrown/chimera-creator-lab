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
stat modal), hall_viewer / hall_grid (finale gallery), battle_clash (FIGHT
tapped with resolve left hanging). DELETE endpoints are never called by the
sweep. Note the page scrolls inside `.screen`, not the window.
"""
import argparse
import json
import os
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
# Profiles, not viewports: the iPad profile runs WEBKIT with Playwright's
# device descriptor for the 10.2" panel (gen 7 == gen 9 screen: 1080x810
# landscape CSS px, DPR 2, touch). Chromium at 1180x820 predicted neither
# mobile-Safari rendering nor the real width — that's how the 2026-08-09
# qa/mobile-safari batch got past the sweep.
PROFILES = {
    "ipad": {"engine": "webkit", "device": "iPad (gen 7) landscape"},
    "desktop": {"engine": "chromium", "viewport": (1440, 900)},
}
# Fallback if the installed Playwright lacks the descriptor.
IPAD_FALLBACK = {
    "viewport": {"width": 1080, "height": 810},
    "device_scale_factor": 2,
    "is_mobile": True,
    "has_touch": True,
    "user_agent": (
        "Mozilla/5.0 (iPad; CPU OS 15_6 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1"
    ),
}
# Portrait smoke shots (the rotate overlay is screen-agnostic; two suffice).
PORTRAIT_SCREENS = ("home", "lab")

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

# The per-screen layout audit. Beyond the font floor it now PREDICTS the
# mobile-Safari failure modes photographed on 2026-08-09:
#   clipped  — text visibly cut by overflow/line-clamp ("RESILIEN…", chips)
#   escapes  — boxes poking out of an overflow-visible parent (crew names,
#              the COMPLETE badge) — FitText can't shrink an unconstrained box
#   overlaps — interactive/panel boxes painting over each other (foot buttons
#              over the bracket, RUN A TOURNAMENT over the finales)
#   imgrisk  — (a) stretch: absolutely positioned images in a well sized only
#              by a stretched track (blank on iPadOS 16.6); (b) in-flow images that would outgrow their parent if their
#              percentage height resolved as auto, which is exactly what
#              iPadOS 16.6 WebKit does inside auto grid rows (the slot-card
#              portraits over their name plates, 2026-09-20)
AUDIT_JS = """
() => {
  const vw = innerWidth, vh = innerHeight;
  const res = { min: null, below: [], hOverflow: 0,
                clipped: [], escapes: [], overlaps: [] };
  res.hOverflow = Math.max(0, document.documentElement.scrollWidth - vw);

  // ── font floor ──
  let min = Infinity;
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
    if (r.bottom < 0 || r.top > vh) continue;
    const fs = parseFloat(cs.fontSize);
    if (!fs) continue;
    if (fs < min) min = fs;
    if (fs < 13)
      below_push(res.below, fs, node.textContent, el);
  }
  function below_push(arr, fs, text, el) {
    arr.push({ px: Math.round(fs * 10) / 10,
               text: text.trim().slice(0, 48),
               cls: String(el.className).slice(0, 60) });
  }
  res.min = isFinite(min) ? Math.round(min * 10) / 10 : null;

  // ── visible element sweep (near-viewport only) ──
  const label = (el) => {
    const raw = el.className;
    const cls = String(raw && raw.baseVal !== undefined ? raw.baseVal : raw || "")
      .trim().split(/\\s+/).slice(0, 2).join(".");
    const txt = (el.textContent || "").trim().replace(/\\s+/g, " ").slice(0, 36);
    return (cls ? "." + cls : el.tagName.toLowerCase()) + (txt ? ` \\"${txt}\\"` : "");
  };
  const vis = [];
  for (const el of document.querySelectorAll("body *")) {
    if (vis.length > 5000) break;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    if (parseFloat(cs.opacity) < 0.05) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    if (r.bottom < -50 || r.top > vh + 400) continue;
    vis.push([el, cs, r]);
  }

  // clipped text (only elements that directly own text)
  for (const [el, cs, r] of vis) {
    const ownText = Array.from(el.childNodes)
      .some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!ownText) continue;
    const clamp = cs.webkitLineClamp && cs.webkitLineClamp !== "none";
    const hidX = cs.overflowX === "hidden" || cs.overflowX === "clip";
    const hidY = cs.overflowY === "hidden" || cs.overflowY === "clip";
    if (hidX && el.scrollWidth > el.clientWidth + 1)
      res.clipped.push({ how: "x", what: label(el) });
    else if (clamp && el.scrollHeight > el.clientHeight + 3)
      res.clipped.push({ how: "clamp", what: label(el) });
    else if (hidY && el.scrollHeight > el.clientHeight + 3)
      res.clipped.push({ how: "y", what: label(el) });
  }

  // escapes from an overflow-visible parent (transformed elements are
  // mid-animation — breathing/pulse effects — not layout bugs)
  for (const [el, cs, r] of vis) {
    const p = el.parentElement;
    if (!p || p === document.body) continue;
    if (cs.position === "absolute" || cs.position === "fixed") continue;
    if (cs.transform !== "none") continue;
    const pcs = getComputedStyle(p);
    if (pcs.overflowX !== "visible" || pcs.display === "contents" ||
        pcs.display === "inline") continue;
    // a clip-path parent visually clips its overflow (the notched cards)
    if (pcs.clipPath && pcs.clipPath !== "none") continue;
    const pr = p.getBoundingClientRect();
    if (pr.width < 8) continue; // boxless/collapsed parent — nothing to escape
    const out = Math.max(pr.left - r.left, r.right - pr.right);
    if (out > 3)
      res.escapes.push({ what: label(el), by: Math.round(out) });
  }

  // overlaps among interactive / panel boxes. Rects are clipped by every
  // scrolling/clipping ancestor first — content scrolled out of an
  // overflow pane isn't painted, so it can't "overlap" anything.
  const clipBy = (el, r) => {
    let left = r.left, top = r.top, right = r.right, bottom = r.bottom;
    for (let a = el.parentElement; a && a !== document.documentElement;
         a = a.parentElement) {
      const acs = getComputedStyle(a);
      if (/(auto|scroll|hidden|clip)/.test(acs.overflowX + acs.overflowY)) {
        const ar = a.getBoundingClientRect();
        left = Math.max(left, ar.left); top = Math.max(top, ar.top);
        right = Math.min(right, ar.right); bottom = Math.min(bottom, ar.bottom);
      }
    }
    return { left, top, right, bottom,
             width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
  };
  // Intentional overlays: the picker rail arrows ride the strip edges and the
  // battle nameplates sit on the arena corners by design.
  // (.summonwait--failed is the TAP TO REPAINT plate that fills a summoned
  // card's well; the ✕ release button is meant to ride on top of it.)
  const INTENTIONAL = ".rail__arrow, .corner__stage, .corner__id, .summonwait--failed";
  const SEL = "button, a, [role=button], .btn, .panel, footer, .fw__spot, " +
              ".predict__ask, .nextmatch, .tile, .pickplate";
  const inFixedOverlay = (el) => {
    for (let a = el; a && a !== document.documentElement; a = a.parentElement)
      if (getComputedStyle(a).position === "fixed") return true;
    return false;
  };
  const cand = vis.filter(([el, cs]) =>
    el.matches(SEL) && !el.matches(INTENTIONAL) &&
    !el.closest("[aria-hidden=true]") && !inFixedOverlay(el))
    .map(([el, cs, r]) => [el, clipBy(el, r)])
    .filter(([, r]) => r.width > 4 && r.height > 4);
  for (let i = 0; i < cand.length && res.overlaps.length < 20; i++) {
    for (let j = i + 1; j < cand.length; j++) {
      const [a, ra] = cand[i], [b, rb] = cand[j];
      if (a.contains(b) || b.contains(a)) continue;
      const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
      const h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
      if (w <= 4 || h <= 4) continue;
      const inter = w * h;
      const small = Math.min(ra.width * ra.height, rb.width * rb.height);
      if (inter > 0.12 * small)
        res.overlaps.push({ a: label(a), b: label(b),
                            pct: Math.round((100 * inter) / small) });
    }
  }
  // ── old-WebKit image escape (Henry's iPad, iPadOS 16.6, 2026-09-20) ──
  // That engine resolves an in-flow image's percentage height against an
  // auto grid row as `auto`, so the image takes its intrinsic size and
  // grows out of its well. Simulate it: give every in-flow image an auto
  // height for a moment and see whether it would then poke out of its
  // parent. Absolutely positioned images resolve against a laid-out box in
  // every engine and are skipped. Anything flagged must get the
  // absolute-image treatment (theme.css, above .slot__art).
  res.imgrisk = [];
  for (const img of document.querySelectorAll("img")) {
    if (res.imgrisk.length >= 24) break;
    const cs = getComputedStyle(img);
    if (cs.display === "none" || cs.position === "absolute" || cs.position === "fixed") continue;
    const p = img.parentElement;
    if (!p) continue;
    // a grid well with ONE definite row the size of the well (the
    // .stage__subject / .rv__hero fix) resolves the percentage everywhere
    const pcs = getComputedStyle(p);
    if (pcs.display === "grid") {
      const rows = pcs.gridTemplateRows.trim().split(/\s+/);
      const inner = p.clientHeight - parseFloat(pcs.paddingTop) - parseFloat(pcs.paddingBottom);
      if (rows.length === 1 && Math.abs(parseFloat(rows[0]) - inner) <= 1) continue;
    }
    const r0 = img.getBoundingClientRect();
    if (r0.width < 2 || r0.height < 2) continue;
    if (r0.bottom < -50 || r0.top > vh + 400) continue;
    if (!img.naturalHeight) continue; // not loaded: nothing to measure
    const saved = [img.style.height, img.style.maxHeight, img.style.minHeight];
    img.style.height = "auto"; img.style.maxHeight = "none"; img.style.minHeight = "0";
    const r1 = img.getBoundingClientRect();
    const pr = p.getBoundingClientRect();
    [img.style.height, img.style.maxHeight, img.style.minHeight] = saved;
    const out = Math.max(r1.bottom - pr.bottom, pr.top - r1.top);
    if (out > 3)
      res.imgrisk.push({ what: label(p), src: (img.getAttribute("src") || "").split("/").pop(),
                         by: Math.round(out) });
  }
  // ── stretch risk (iPadOS 16.6, photographed 2026-09-20) ──
  // A well holding an absolutely positioned image whose own height comes
  // ONLY from a stretched grid/flex track: old WebKit lays the image out
  // before the stretch and never revisits it, so the well paints empty
  // (bracket-setup cards, lab slot cards). Probe: pin the well to the start
  // of its track for a moment; if it shrinks, its height was stretch-derived
  // and it needs an explicit height / aspect-ratio (theme.css .ccard__art).
  for (const img of document.querySelectorAll("img.asset, .pending, .summonwait")) {
    if (res.imgrisk.length >= 24) break;
    const cs = getComputedStyle(img);
    if (cs.position !== "absolute") continue;
    const p = img.parentElement;
    if (!p || !p.parentElement) continue;
    const pr0 = p.getBoundingClientRect();
    if (pr0.height < 4 || pr0.bottom < -50 || pr0.top > vh + 400) continue;
    const gp = getComputedStyle(p.parentElement).display;
    if (!/grid|flex/.test(gp)) continue;
    const saved = [p.style.alignSelf, p.style.flexGrow, p.style.flexShrink];
    p.style.alignSelf = "start"; p.style.flexGrow = "0"; p.style.flexShrink = "0";
    const pr1 = p.getBoundingClientRect();
    [p.style.alignSelf, p.style.flexGrow, p.style.flexShrink] = saved;
    const lost = pr0.height - pr1.height;
    if (lost > 3)
      res.imgrisk.push({ what: label(p), kind: "stretch",
                         src: (img.getAttribute("src") || "").split("/").pop(), by: Math.round(lost) });
  }
  res.below = res.below.slice(0, 24);
  res.clipped = res.clipped.slice(0, 24);
  res.escapes = res.escapes.slice(0, 24);
  return res;
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


_COOKIE: str | None = None


def login(base: str) -> None:
    """The PIN gate (armed on prod 2026-08-10) guards every /api read this
    script derives real ids from — the urllib side must log in too, not just
    the browser contexts, or build_screens silently loses reveal/bracket/
    battle and the sweep crashes at battle_scout."""
    global _COOKIE
    pin = os.environ.get("CHIMERA_PIN")
    if not pin:
        return
    req = urllib.request.Request(
        f"{base}/api/auth/login",
        data=json.dumps({"pin": pin}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            for header in r.headers.get_all("Set-Cookie") or []:
                if header.startswith("chimera_session="):
                    _COOKIE = header.split(";", 1)[0]
    except Exception as exc:
        print(f"  (login failed: {exc} — data-derived screens may be missing)")


def fetch_json(base: str, path: str):
    try:
        req = urllib.request.Request(f"{base}{path}")
        if _COOKIE:
            req.add_header("Cookie", _COOKIE)
        with urllib.request.urlopen(req, timeout=5) as r:
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
    login(base)
    SCREENS = build_screens(base)
    errors: dict[str, list[str]] = {}
    fonts: dict[str, dict] = {}
    stubbed = ["tournaments/current (arena, arena_setup)", "fw_a", "fw_b", "fw_c"]

    current_body = current_payload(base)

    # A complete tournament re-served with one championship match unresolved —
    # the raw material for the battle_predict shot.
    predict_stub = None
    tours = fetch_json(base, "/api/tournaments") or []
    for t in tours:
        import copy
        t2 = copy.deepcopy(t)
        tgt = next((m for rnd in t2.get("rounds", []) for m in rnd.get("matches", [])
                    if m.get("winner") is not None and m.get("a") and m.get("b")), None)
        if tgt:
            tgt["winner"] = None
            tgt["battle_id"] = None
            tgt["predicted"] = None
            t2["status"] = "active"
            predict_stub = (t2, tgt["id"])
            break

    with sync_playwright() as pw:
        browsers: dict[str, object] = {}

        def engine(name: str):
            if name not in browsers:
                browsers[name] = getattr(pw, name).launch()
            return browsers[name]

        def make_ctx(prof: dict):
            if "device" in prof:
                desc = dict(pw.devices.get(prof["device"]) or IPAD_FALLBACK)
                desc.pop("default_browser_type", None)
                ctx = engine(prof["engine"]).new_context(**desc)
            else:
                w, h = prof["viewport"]
                ctx = engine(prof["engine"]).new_context(
                    viewport={"width": w, "height": h}, device_scale_factor=2)
            # Once the PIN gate ships, the sweep authenticates like Henry does.
            pin = os.environ.get("CHIMERA_PIN")
            if pin:
                try:
                    ctx.request.post(f"{base}/api/auth/login", data={"pin": pin})
                except Exception:
                    pass
            return ctx

        for vp_name, prof in PROFILES.items():
            ctx = make_ctx(prof)
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
                a = page.evaluate(AUDIT_JS)
                fonts[key[0]] = a
                flags = []
                if a["hOverflow"]:
                    flags.append(f"hoverflow {a['hOverflow']}px")
                for k in ("clipped", "escapes", "overlaps", "imgrisk"):
                    if a.get(k):
                        flags.append(f"{k} {len(a[k])}")
                print(f"  shot {name}_{vp_name}  (min font {a['min']}px"
                      + (";  " + ", ".join(flags) if flags else "") + ")")

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

            if "battle" in SCREENS:  # absent on a dataset with no fought battles
                shot("battle_scout", SCREENS["battle"][0], SCREENS["battle"][1], open_scout)

            # Hall: the finale viewer (first painting) and the gallery grid.
            # Taps go through el.click(): Playwright's own hit-test misplaces
            # points inside a position:fixed overlay under WebKit iPad
            # emulation (2026-09-20), and the viewer is one.
            def open_viewer():
                try:
                    page.click(".gcard >> nth=0", timeout=3000)
                    page.wait_for_timeout(1500)
                    page.evaluate("document.querySelector('.viewer__arrow--r')?.click()")
                    page.wait_for_timeout(1200)
                except Exception:
                    print("  (hall_viewer: no finale cards)")

            shot("hall_viewer", SCREENS["hall"][0], SCREENS["hall"][1], open_viewer)

            def open_grid():
                try:
                    # same hash as the previous shot: no remount, so the
                    # viewer may still be open over the SEE ALL button
                    page.evaluate("document.querySelector('.viewer__close')?.click()")
                    page.wait_for_timeout(300)
                    page.click("text=SEE ALL", timeout=3000)
                    page.wait_for_timeout(1500)
                except Exception:
                    print("  (hall_grid: no SEE ALL button)")

            shot("hall_grid", SCREENS["hall"][0], SCREENS["hall"][1], open_grid)

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

            # The predict state — "WHO DO YOU THINK WINS?" only renders on an
            # unresolved match, so a resolved one is served back with its
            # winner nulled. Every write verb is blocked: the sweep must never
            # fire a real AI battle.
            if predict_stub:
                t2, mid = predict_stub
                def block_writes(route):
                    if route.request.method in ("POST", "PUT", "PATCH", "DELETE"):
                        route.abort()
                    else:
                        route.fallback()
                body2 = json.dumps(t2)

                def stub_t(route, _request=None, body=body2):
                    route.fulfill(status=200, content_type="application/json",
                                  body=body)

                page.route("**/api/tournaments/**", block_writes)
                page.route(f"**/api/tournaments/{t2['id']}", stub_t)
                shot("battle_predict", f"#/arena/{t2['id']}/{mid}", 3200)
                page.unroute(f"**/api/tournaments/{t2['id']}")
                page.unroute("**/api/tournaments/**")

                # The CLASH: FIGHT tapped, the verdict never arrives (resolve
                # is left hanging, never fulfilled) — the theatre stays up.
                def hang_resolve(route):
                    if route.request.method in ("POST", "PUT", "PATCH", "DELETE"):
                        if not route.request.url.endswith("/resolve"):
                            route.abort()
                    else:
                        route.fallback()

                def tap_fight():
                    try:
                        page.click("text=FIGHT!", timeout=3000)
                        page.wait_for_timeout(1800)
                    except Exception:
                        print("  (battle_clash: FIGHT not clickable)")

                page.route("**/api/tournaments/**", hang_resolve)
                page.route(f"**/api/tournaments/{t2['id']}", stub_t)
                shot("battle_clash", f"#/arena/{t2['id']}/{mid}", 3200, tap_fight)
                page.unroute(f"**/api/tournaments/{t2['id']}")
                page.unroute("**/api/tournaments/**")
            ctx.close()

        # Portrait smoke shots — verifies the rotate-to-landscape overlay
        # (and that nothing renders catastrophically underneath it).
        desc = dict(pw.devices.get("iPad (gen 7)") or
                    {**IPAD_FALLBACK,
                     "viewport": {"width": 810, "height": 1080}})
        desc.pop("default_browser_type", None)
        ctx = engine("webkit").new_context(**desc)
        page = ctx.new_page()
        key = [""]
        for name in PORTRAIT_SCREENS:
            route, settle = SCREENS[name]
            key[0] = f"{name}:ipad_portrait"
            page.goto(f"{base}/{route}")
            page.wait_for_timeout(settle)
            page.screenshot(path=str(out / f"{name}_ipad_portrait.png"))
            fonts[key[0]] = page.evaluate(AUDIT_JS)
            print(f"  shot {name}_ipad_portrait")
        ctx.close()

        for b in browsers.values():
            b.close()

    (out / "console.json").write_text(json.dumps(errors, indent=2))
    (out / "audit.json").write_text(json.dumps(fonts, indent=2))
    (out / "stubbed.json").write_text(json.dumps(stubbed, indent=2))

    bad = {k: v for k, v in errors.items() if v}
    print(f"\nconsole errors on {len(bad)} screen(s)" + (f": {list(bad)}" if bad else ""))

    print("\nper-screen audit (font floor 13px; clip/escape/overlap should be 0):")
    for k in sorted(fonts):
        f = fonts[k]
        flag = "  <-- BELOW FLOOR" if (f["min"] or 99) < 13 else ""
        counts = "  ".join(
            f"{n}:{len(f.get(n) or [])}" for n in ("clipped", "escapes", "overlaps", "imgrisk"))
        hov = f.get("hOverflow") or 0
        print(f"  {k:28s} min {f['min']}px  {counts}  hoverflow:{hov}{flag}")
    print("\nflagged details:")
    any_flag = False
    for k in sorted(fonts):
        f = fonts[k]
        for n in ("clipped", "escapes", "overlaps", "imgrisk"):
            for item in (f.get(n) or [])[:8]:
                any_flag = True
                print(f"  {k:26s} {n:8s} {json.dumps(item, ensure_ascii=False)}")
    if not any_flag:
        print("  (none — clean sweep)")

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
