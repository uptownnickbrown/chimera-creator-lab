"""Shared chimera specs + style prompts for the image-model bakeoff."""

STYLE = (
    "Epic realistic fantasy creature concept art for a AAA video game. "
    "Cinematic dramatic lighting, hyper-detailed textures, museum-quality "
    "creature design. The creature is ONE coherent invented species, not "
    "animals stitched together. Full body visible, dynamic three-quarter "
    "hero pose, looking slightly toward the viewer, jaws open in a roar. "
    "Serious, awe-inspiring, worthy of a movie poster — but suitable for a "
    "7-year-old: fierce and epic, no gore, no blood. "
    "Absolutely no text, letters, numbers, logos, or watermarks."
)

CHROMA = (
    " The entire background must be one single flat, uniform, solid bright "
    "magenta color #FF00FF with no gradient, no vignette, no fog, no texture "
    "and no shadows cast onto it. Do not use pink, magenta or purple anywhere "
    "on the creature itself. The creature must not touch the edges of the image."
)

SPECS = {
    "stormback": {
        "name": "Stormback Leviadrake",
        "sources": ["Dragon", "Stegosaurus", "Electric Eel", "Shark"],
        "prompt": (
            "A colossal armored storm-leviathan fusing dragon, stegosaurus, "
            "electric eel, and great white shark into one species. Dragon: "
            "horned reptilian head, curved obsidian claws, smoldering breath. "
            "Stegosaurus: a double row of massive jagged back plates crackling "
            "with energy. Electric eel: sleek bio-electric organs along its "
            "flanks, arcs of blue-white lightning dancing across its body. "
            "Shark: powerful crescent tail fin, rows of serrated teeth, grey "
            "hydrodynamic hide with a pale underbelly. Quadrupedal stance, "
            "muscular, storm-charged."
        ),
    },
    "basilodion": {
        "name": "Basilodion",
        "sources": ["Basilisk", "Megalodon", "Lobster", "Electric Eel"],
        "prompt": (
            "A nightmarish deep-sea tyrant fusing basilisk, megalodon, lobster, "
            "and electric eel into one species. Basilisk: piercing hypnotic "
            "yellow serpent eyes, crowned spined head crest, venomous fangs. "
            "Megalodon: titanic shark body mass, enormous jaws with rows of "
            "huge teeth, dark dorsal fin. Lobster: segmented crimson-black "
            "armored exoskeleton plates and two massive crushing pincer claws. "
            "Electric eel: long sinuous tail wreathed in violet-blue electric "
            "discharge. Rising from churning surf, armored and immense."
        ),
    },
    "tideburn": {
        "name": "Tideburn Aurion",
        "sources": ["Phoenix", "Saber-Toothed Tiger", "Walrus", "Salmon"],
        "prompt": (
            "A majestic fire-and-water beast fusing phoenix, saber-toothed "
            "tiger, walrus, and salmon into one species. Phoenix: huge blazing "
            "wings of living flame, ember-glow mane of fiery feathers. "
            "Saber-toothed tiger: muscular feline face and forequarters with "
            "two enormous curved saber fangs and clawed forepaws. Walrus: "
            "massive blubbery lower body, thick ivory tusks, whiskered muzzle "
            "blended into the feline face. Salmon: iridescent silver-red "
            "scaled hindquarters and a powerful finned tail, water streaming "
            "off it. Fire meeting water, steam rising, epic and noble."
        ),
    },
}
