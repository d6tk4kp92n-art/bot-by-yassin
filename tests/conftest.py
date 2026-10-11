"""Outils partagés par les tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def champ(nom: str, valeur: str) -> dict[str, str]:
    return {"name": nom, "value": f"```\n{valeur}\n```"}


def embed_exemple(
    user: str = "yayaoui00",
    zone: str = "Safe",
    gold_drop: str = "3,851",
    gems: str = "37,807",
    gold_total: str = "81,508",
) -> dict:
    """L'embed d'exemple donné dans le cahier des charges."""
    return {
        "title": "Tekkit | Rewards Logger",
        "fields": [
            champ("User:", user),
            champ(
                "Player Stats:",
                f"Prestige: 3\nLevel: 31\nGems: {gems}\nGold: {gold_total}",
            ),
            champ("Mission Stats:", "Time Taken: 01:04\nDifficulty: Easy"),
            champ(
                "Drops:",
                f"Gold: {gold_drop}\nXP: 1,442\nEnhanced Metabolism (Common)\nLucky (Common)",
            ),
            champ("Safety Status:", zone),
        ],
    }


@pytest.fixture
def embed():
    return embed_exemple()
