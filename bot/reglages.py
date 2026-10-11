"""Réglages modifiables : gardés en mémoire ET enregistrés en base immédiatement."""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any

from bot.config import DEFAUTS, NB_COMPTES_MAX, defauts
from bot.database import Database

RE_USERNAME = re.compile(r"^[A-Za-z0-9_]{3,20}$")  # format d'un username Roblox


class Reglages(Mapping[str, Any]):
    """Se lit comme un dictionnaire : reglages["delai_absence_min"]."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._valeurs: dict[str, Any] = defauts()

    async def charger(self) -> None:
        """Lit la base et complète avec les valeurs par défaut."""
        self._valeurs = defauts()
        for cle, valeur in (await self.db.lire_reglages()).items():
            if cle in DEFAUTS and _meme_type(valeur, DEFAUTS[cle]):
                self._valeurs[cle] = valeur

    async def definir(self, cle: str, valeur: Any) -> None:
        """Change un réglage et l'enregistre tout de suite en base."""
        if cle not in DEFAUTS:
            raise KeyError(f"Réglage inconnu : {cle}")
        self._valeurs[cle] = copy.deepcopy(valeur)
        await self.db.ecrire_reglage(cle, valeur)

    async def basculer(self, cle: str) -> bool:
        """Inverse un réglage oui/non et renvoie la nouvelle valeur."""
        nouvelle = not bool(self._valeurs.get(cle))
        await self.definir(cle, nouvelle)
        return nouvelle

    async def tout_remettre_par_defaut(self) -> None:
        await self.db.effacer_reglages(garder_prefixe="_")
        internes = {k: v for k, v in self._valeurs.items() if k.startswith("_")}
        self._valeurs = defauts()
        self._valeurs.update(internes)

    def exporter(self) -> dict[str, Any]:
        """Réglages visibles (sans l'état interne), pour la sauvegarde."""
        return {k: copy.deepcopy(v) for k, v in self._valeurs.items() if not k.startswith("_")}

    async def importer(self, donnees: Mapping[str, Any]) -> list[str]:
        """Applique des réglages sauvegardés. Renvoie les clés acceptées."""
        acceptees = []
        for cle, valeur in donnees.items():
            if cle == "comptes" and isinstance(valeur, list):
                valeur = [
                    str(c).strip()
                    for c in valeur
                    if isinstance(c, str) and RE_USERNAME.match(c.strip())
                ]
                valeur = list(dict.fromkeys(valeur))[:NB_COMPTES_MAX]
            if cle in DEFAUTS and not cle.startswith("_") and _meme_type(valeur, DEFAUTS[cle]):
                await self.definir(cle, valeur)
                acceptees.append(cle)
        return acceptees

    # Interface Mapping
    def __getitem__(self, cle: str) -> Any:
        return self._valeurs[cle]

    def __iter__(self):
        return iter(self._valeurs)

    def __len__(self) -> int:
        return len(self._valeurs)


def _meme_type(valeur: Any, defaut: Any) -> bool:
    """Évite qu'une valeur abîmée en base (mauvais type) casse le bot."""
    if defaut is None:
        return valeur is None or isinstance(valeur, (int, str))
    if isinstance(defaut, bool):
        return isinstance(valeur, bool)
    if isinstance(defaut, int):
        return isinstance(valeur, int) and not isinstance(valeur, bool)
    return isinstance(valeur, type(defaut))
