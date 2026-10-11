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


FAUX_TOKEN = "MTIzNDU2Nzg5MDEyMzQ1Njc4.faux.token_de_test_qui_ne_marche_pas"
OWNER_ID = 111
SALON_WEBHOOK = 222


class FauxClientOllama:
    """Ollama simulé : répond ce qu'on lui dit, note les appels, peut être « éteint »."""

    def __init__(self, reponses=None, modeles=("qwen3.5:4b",), eteint=False, lenteur=0.0):
        self.url = "http://localhost:11434"
        self.reponses = list(reponses or [])
        self.modeles = list(modeles)
        self.eteint = eteint
        self.lenteur = lenteur
        self.appels = []
        self.en_cours = 0
        self.max_en_cours = 0

    def _verifier(self):
        if self.eteint:
            from bot.ia_moteur import OllamaAbsent

            raise OllamaAbsent(self.url)

    async def tags(self, delai=5):
        self._verifier()
        return [{"name": m} for m in self.modeles]

    async def ps(self):
        self._verifier()
        return [{"name": self.modeles[0], "size": 3 * 1024**3}] if self.modeles else []

    async def chat(self, corps, delai):
        import asyncio

        self._verifier()
        self.appels.append(corps)
        self.en_cours += 1
        self.max_en_cours = max(self.max_en_cours, self.en_cours)
        try:
            if self.lenteur:
                await asyncio.sleep(self.lenteur)
            reponse = (
                self.reponses.pop(0)
                if self.reponses
                else {"message": {"role": "assistant", "content": "ok"}}
            )
            if isinstance(reponse, Exception):
                raise reponse
            return reponse
        finally:
            self.en_cours -= 1

    async def fermer(self):
        pass


@pytest.fixture
async def bot(tmp_path):
    """Un vrai TekkitBot, prêt, mais jamais connecté à Discord (faux token)."""
    from bot.config import Config
    from bot.main import TekkitBot

    config = Config(token=FAUX_TOKEN, owner_id=OWNER_ID, webhook_channel_id=SALON_WEBHOOK)
    b = TekkitBot(config, chemin_base=tmp_path / "test.db")
    async with b:  # initialise le client sans se connecter
        await b.preparer()
        b.get_cog("IA").moteur.client = FauxClientOllama()
        yield b
        for nom in list(b.extensions):
            await b.unload_extension(nom)
