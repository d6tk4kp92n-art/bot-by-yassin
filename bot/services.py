"""Rassemble les données (base + état de la surveillance) pour les résumés, stats, IA...

Les cogs et l'IA passent par ici : un seul endroit qui sait « où sont les chiffres ».
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from bot.calculs import (
    FENETRE_RYTHME_S,
    Estimation,
    Gains,
    Rythme,
    StatsCompte,
    bornes_periode,
    est_rare,
    estimer,
    gains,
    rythme,
    stats_compte,
    taux_par_heure,
    taux_total_par_heure,
)
from bot.database import Database, DropEnregistre, Evenement
from bot.moteur_surveillance import MoteurSurveillance
from bot.parser import Mission, zone_est_safe
from bot.reglages import Reglages

TYPES_OBJECTIF: dict[str, str] = {
    "gems": "💎 Gems",
    "gold": "💰 Gold",
    "level": "⭐ Niveau",
    "prestige": "🏅 Prestige",
    "missions": "🎯 Missions",
}


@dataclass
class EtatCompteResume:
    """Tout ce qu'il faut pour afficher un compte dans le résumé."""

    nom: str
    en_ligne: bool | None
    derniere: Mission | None
    gains: Gains
    session: Gains
    rythme: Rythme | None
    estimation: Estimation | None
    evenements: list[Evenement] = field(default_factory=list)

    @property
    def zone(self) -> str | None:
        return self.derniere.zone if self.derniere else None

    @property
    def est_safe(self) -> bool | None:
        return zone_est_safe(self.zone)


@dataclass
class EstimationCompte:
    nom: str
    estimation: Estimation | None
    en_ligne: bool | None


class Services:
    def __init__(
        self, db: Database, reglages: Reglages, moteur: MoteurSurveillance, demarrage: float
    ) -> None:
        self.db = db
        self.reglages = reglages
        self.moteur = moteur
        self.demarrage = demarrage

    @property
    def comptes(self) -> list[str]:
        return list(self.reglages["comptes"])

    def delai_absence_s(self) -> int:
        return max(1, int(self.reglages["delai_absence_min"])) * 60

    # ------------------------------------------------------------ rythmes

    async def missions_pour_rythme(
        self, compte: str, maintenant: float, fenetre_s: float = FENETRE_RYTHME_S
    ) -> list[Mission]:
        """Missions de la fenêtre + la dernière juste avant (pour savoir s'il y a de l'historique)."""
        debut = maintenant - fenetre_s
        liste = await self.db.missions(compte=compte, debut=debut, fin=maintenant)
        avant = await self.db.derniere_mission_avant(compte, debut)
        return ([avant] if avant else []) + liste

    async def rythme_compte(self, compte: str, maintenant: float | None = None) -> Rythme | None:
        maintenant = maintenant or time.time()
        return rythme(await self.missions_pour_rythme(compte, maintenant), maintenant)

    def en_ligne(self, compte: str, maintenant: float) -> bool | None:
        return self.moteur.est_en_ligne(compte, maintenant, self.delai_absence_s())

    # ------------------------------------------------------------ résumé

    async def etat_comptes(self, maintenant: float | None = None) -> list[EtatCompteResume]:
        maintenant = maintenant or time.time()
        raretes = self.reglages["raretes"]
        periode_s = max(1, int(self.reglages["periode_gains_min"])) * 60
        heures = float(self.reglages["estimation_heures"])
        resultat = []
        for nom in self.comptes:
            derniere = await self.db.derniere_mission(nom)
            recentes = await self.db.missions(
                compte=nom, debut=maintenant - periode_s, avec_drops=True
            )
            session = await self.db.missions(compte=nom, debut=self.demarrage, avec_drops=True)
            r = await self.rythme_compte(nom, maintenant)
            resultat.append(
                EtatCompteResume(
                    nom=nom,
                    en_ligne=self.en_ligne(nom, maintenant),
                    derniere=derniere,
                    gains=gains(recentes, raretes),
                    session=gains(session, raretes),
                    rythme=r,
                    estimation=estimer(r, heures) if r else None,
                    evenements=await self.db.evenements(
                        nom, depuis=maintenant - 6 * 3600, limite=3
                    ),
                )
            )
        return resultat

    # ------------------------------------------------------------ estimations

    async def estimations(
        self, heures: float, maintenant: float | None = None
    ) -> list[EstimationCompte]:
        maintenant = maintenant or time.time()
        resultat = []
        for nom in self.comptes:
            r = await self.rythme_compte(nom, maintenant)
            resultat.append(
                EstimationCompte(
                    nom, estimer(r, heures) if r else None, self.en_ligne(nom, maintenant)
                )
            )
        return resultat

    # ------------------------------------------------------------ stats

    async def bornes(self, periode: str, maintenant: float | None = None) -> tuple[float, float]:
        maintenant = maintenant or time.time()
        premiere = await self.db.premiere_mission() if periode == "tout" else None
        return bornes_periode(periode, maintenant, self.demarrage, premiere)

    async def stats(
        self, periode: str, maintenant: float | None = None, comptes: list[str] | None = None
    ) -> list[StatsCompte]:
        debut, fin = await self.bornes(periode, maintenant)
        resultat = []
        for nom in comptes or self.comptes:
            missions = await self.db.missions(compte=nom, debut=debut, fin=fin, avec_drops=True)
            resultat.append(
                stats_compte(
                    nom, missions, debut, fin, self.delai_absence_s(), self.reglages["raretes"]
                )
            )
        return resultat

    async def drops_rares(
        self, compte: str | None, rarete_min: str, periode: str = "tout", limite: int = 200
    ) -> list[DropEnregistre]:
        debut, fin = await self.bornes(periode)
        raretes = self.reglages["raretes"]
        voulues = [r for r in raretes if est_rare(r, rarete_min, raretes)]
        # On inclut aussi les variantes connues (ex. « Mythical » pour « Mythic »)
        if "Mythic" in voulues:
            voulues.append("Mythical")
        return await self.db.drops(
            compte=compte, raretes=voulues, debut=debut, fin=fin, limite=limite
        )

    # ------------------------------------------------------------ objectifs

    async def valeur_actuelle(self, compte: str, type_: str) -> int | None:
        if type_ == "missions":
            return await self.db.nombre_missions(compte)
        derniere = await self.db.derniere_mission(compte)
        if derniere is None:
            return None
        return {
            "gems": derniere.gems_total,
            "gold": derniere.gold_total,
            "level": derniere.level,
            "prestige": derniere.prestige,
        }.get(type_)

    async def taux_objectif(
        self, compte: str, type_: str, maintenant: float | None = None
    ) -> float | None:
        """Progression par heure sur les 6 dernières heures."""
        maintenant = maintenant or time.time()
        fenetre = 6 * 3600
        missions = await self.missions_pour_rythme(compte, maintenant, fenetre)
        if type_ == "missions":
            return taux_par_heure([(m.horodatage, 1.0) for m in missions], maintenant, fenetre)
        attribut = {
            "gems": "gems_total",
            "gold": "gold_total",
            "level": "level",
            "prestige": "prestige",
        }.get(type_)
        if attribut is None:
            return None
        points = [
            (m.horodatage, float(v)) for m in missions if (v := getattr(m, attribut)) is not None
        ]
        return taux_total_par_heure(points, maintenant, fenetre)
