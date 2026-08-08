#!/usr/bin/env python3
"""Regenerate henry_a with stronger likeness from the new close-up photo."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from assetlib import finalize, generate

PICS = Path.home() / "Downloads" / "henry-pics"
p = generate(
    "Stylized hero avatar portrait for a cinematic neon sci-fi game, of the "
    "SAME BOY shown in the attached reference photos — match his face "
    "closely: side-swept golden-blond fringe falling over his forehead, "
    "fair skin, warm brown eyes, his exact huge open-mouthed grin with "
    "slightly big front teeth, age 8. He wears a sleek white-and-navy "
    "junior scientist lab coat with glowing cyan trim, holographic goggles "
    "pushed up into his hair. Premium painterly game-art rendering "
    "(kid-friendly realistic proportions, NOT cartoon chibi), dramatic cyan "
    "and violet lab rim-lighting. Pose: standing tall, three-quarter view, "
    "arms crossed, that huge confident grin. Full body, centered, not "
    "touching edges, transparent background. No text or watermarks.",
    "avatar_henry_a", size="1024x1024", transparent=True,
    references=[str(PICS / "IMG_3523_henry.jpg"), str(PICS / "IMG_2552.jpg")])
finalize(p, "avatar/henry_a", 512, 512)
print("henry_a regenerated")
