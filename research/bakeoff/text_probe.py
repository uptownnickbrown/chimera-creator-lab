#!/usr/bin/env python3
"""Probe text models for the structured creature-record generation contract.

Same fresh combo (never in examples) through several models; measures latency
and dumps each record for quality review. Fresh combo: Kraken + Woolly Mammoth
+ Chameleon + Peregrine Falcon.
"""

import concurrent.futures as cf
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)

COMBO = ["Kraken", "Woolly Mammoth", "Chameleon", "Peregrine Falcon"]

SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Exciting 1-3 word species name a 7-year-old can pronounce, hinting at 1-2 component traits"},
        "title": {"type": "string", "description": "Epic short title like 'The Thundered Leviathan'"},
        "anatomy_plan": {"type": "string", "description": "How the four sources map to body systems, one coherent species"},
        "core_stats": {
            "type": "object",
            "properties": {
                "power": {"type": "integer"}, "speed": {"type": "integer"},
                "armor": {"type": "integer"}, "size": {"type": "integer"},
                "special_name": {"type": "string", "description": "Creature-specific 5th stat name, one word, e.g. Venom, Flight, Stealth"},
                "special": {"type": "integer"},
            },
            "required": ["power", "speed", "armor", "size", "special_name", "special"],
            "additionalProperties": False,
        },
        "abilities": {
            "type": "array", "minItems": 3, "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "blurb": {"type": "string", "description": "One short exciting sentence a 7-year-old can read"},
                    "sources": {"type": "array", "items": {"type": "string"}, "description": "Which source creatures combine into this ability — best abilities fuse two"},
                },
                "required": ["name", "blurb", "sources"], "additionalProperties": False,
            },
        },
        "strengths": {"type": "array", "items": {"type": "string"}, "description": "2-3 scannable phrases like 'Fast in water'"},
        "weaknesses": {"type": "array", "items": {"type": "string"}, "description": "2-3 real weaknesses, e.g. 'Heavy armor makes it slow to turn'"},
        "environment_affinities": {
            "type": "object",
            "description": "Score -2 (terrible) to +2 (dominant) per environment",
            "properties": {k: {"type": "integer"} for k in
                ["deep_ocean", "storm_coast", "volcanic_shore", "jungle_canyon",
                 "frozen_ridge", "open_sky", "desert_ruins", "swamp", "city_harbor"]},
            "required": ["deep_ocean", "storm_coast", "volcanic_shore", "jungle_canyon",
                         "frozen_ridge", "open_sky", "desert_ruins", "swamp", "city_harbor"],
            "additionalProperties": False,
        },
        "sim_profile": {
            "type": "object",
            "description": "Hidden simulation stats 0-100",
            "properties": {k: {"type": "integer"} for k in
                ["land_speed", "swim_speed", "flight_speed", "bite_force", "armor_rating",
                 "intelligence", "endurance", "regeneration", "attack_range", "maneuverability"]},
            "required": ["land_speed", "swim_speed", "flight_speed", "bite_force", "armor_rating",
                         "intelligence", "endurance", "regeneration", "attack_range", "maneuverability"],
            "additionalProperties": False,
        },
        "visual_spec": {"type": "string", "description": "Detailed image-generation description of the creature's appearance: colors, textures, body plan, signature features"},
        "rarity": {"type": "string", "enum": ["Uncommon", "Rare", "Epic", "Legendary"]},
        "fun_fact": {"type": "string", "description": "One delightful fact a kid would repeat to a friend"},
    },
    "required": ["name", "title", "anatomy_plan", "core_stats", "abilities", "strengths",
                 "weaknesses", "environment_affinities", "sim_profile", "visual_spec",
                 "rarity", "fun_fact"],
    "additionalProperties": False,
}

SYSTEM = (
    "You are the creature engine for Chimera Creator, a game where a 7-year-old "
    "fuses four real/mythic creatures into one spectacular new species. Invent ONE "
    "coherent species (never four animals stitched together). Best abilities fuse "
    "TWO sources (e.g. Shark + Electric Eel = Thunder Bite). Every creature needs "
    "real weaknesses — resist 'awesome at everything'. Stats 0-100, honest spread, "
    "not all 90s. Kid-readable language: short, punchy, epic but not gory."
)

PROMPT = f"Create a chimera from these four sources: {', '.join(COMBO)}."


def probe_openai(model: str) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPEN_AI_API_KEY"], timeout=180)
    t0 = time.time()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": PROMPT}],
        response_format={"type": "json_schema",
                         "json_schema": {"name": "chimera", "strict": True, "schema": SCHEMA}},
    )
    dt = time.time() - t0
    rec = json.loads(resp.choices[0].message.content)
    return {"model": model, "latency_s": round(dt, 1), "record": rec}


def probe_gemini(model: str) -> dict:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    t0 = time.time()
    resp = client.models.generate_content(
        model=model,
        contents=PROMPT,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
        ),
    )
    dt = time.time() - t0
    return {"model": model, "latency_s": round(dt, 1), "record": json.loads(resp.text)}


def main():
    jobs = {
        "gpt-5.1": lambda: probe_openai("gpt-5.1"),
        "gpt-5-mini": lambda: probe_openai("gpt-5-mini"),
        "gemini-3-pro-preview": lambda: probe_gemini("gemini-3-pro-preview"),
        "gemini-3-flash-preview": lambda: probe_gemini("gemini-3-flash-preview"),
    }
    out = {}
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fn): name for name, fn in jobs.items()}
        for fut in cf.as_completed(futs):
            name = futs[fut]
            try:
                out[name] = fut.result()
                print(f"OK  {name:<24} {out[name]['latency_s']}s  name={out[name]['record']['name']!r}")
            except Exception as e:
                out[name] = {"error": f"{type(e).__name__}: {e}"}
                print(f"ERR {name}: {str(e)[:200]}")
    (HERE / "text_results.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
