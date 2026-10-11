"""Cœur de la surveillance : décide QUAND alerter. Aucune dépendance à Discord.

Le cog `cogs/surveillance.py` appelle ce moteur et se contente d'envoyer les alertes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bot.calculs import Anomalie, est_rare, formater_duree, normaliser_rarete
from bot.parser import Mission, zone_est_safe

DELAI_REPETITION_ANOMALIE_S = 30 * 60  # une même anomalie n'est pas répétée avant 30 min

# Couleurs des alertes
ROUGE = 0xED4245
VERT = 0x57F287
ORANGE = 0xE67E22
VIOLET = 0x9B59B6
JAUNE = 0xFEE75C


@dataclass
class Alerte:
    """Une alerte à envoyer sur Discord."""

    type: str  # disparition, retour, zone_quitte, zone_retour, drop, anomalie
    compte: str
    titre: str
    texte: str
    ping: bool
    couleur: int
    horodatage: float


@dataclass
class EtatCompte:
    """Ce que le moteur sait d'un compte."""

    nom: str
    derniere_vue: float | None = None
    reference: float = 0.0  # début du compte à rebours (démarrage, reprise ou dernière mission)
    absent_signale: bool = False
    zone: str | None = None
    anomalies: dict[str, float] = field(default_factory=dict)  # type -> dernière alerte

    def depuis(self, maintenant: float) -> float:
        """Secondes écoulées depuis la dernière activité (ou le début du compte à rebours)."""
        return maintenant - max(self.derniere_vue or 0.0, self.reference)


class MoteurSurveillance:
    def __init__(self, demarrage: float) -> None:
        self.demarrage = demarrage
        self.pause = False
        self._etats: dict[str, EtatCompte] = {}

    # ------------------------------------------------------------ comptes

    def configurer(self, comptes: Iterable[str]) -> None:
        """Synchronise la liste des comptes surveillés (ajouts/retraits)."""
        voulus = {c.strip().casefold(): c.strip() for c in comptes if c and c.strip()}
        for cle in list(self._etats):
            if cle not in voulus:
                del self._etats[cle]
        for cle, nom in voulus.items():
            if cle not in self._etats:
                self._etats[cle] = EtatCompte(nom=nom, reference=self.demarrage)
            else:
                self._etats[cle].nom = nom

    def etat(self, compte: str) -> EtatCompte | None:
        return self._etats.get(compte.strip().casefold())

    @property
    def comptes(self) -> list[str]:
        return [e.nom for e in self._etats.values()]

    def restaurer(self, compte: str, derniere_vue: float | None, zone: str | None) -> None:
        """Au démarrage : reprend la dernière activité connue en base, sans alerter.

        Le compte à rebours part quand même du démarrage du bot (chaque compte a X min)."""
        e = self.etat(compte)
        if e is None:
            return
        e.derniere_vue = derniere_vue
        e.zone = zone

    def est_en_ligne(self, compte: str, maintenant: float, delai_s: float) -> bool | None:
        """True = actif, False = absent, None = jamais vu."""
        e = self.etat(compte)
        if e is None or e.derniere_vue is None:
            return None
        return (maintenant - e.derniere_vue) < delai_s and not e.absent_signale

    # ------------------------------------------------------------ pause

    def mettre_en_pause(self) -> None:
        self.pause = True

    def reprendre(self, maintenant: float) -> None:
        """À la reprise, chaque compte a de nouveau X minutes pour réapparaître."""
        self.pause = False
        for e in self._etats.values():
            e.reference = maintenant
            e.absent_signale = False

    # ------------------------------------------------------------ vérification périodique

    def verifier(self, maintenant: float, reglages: Mapping[str, Any]) -> list[Alerte]:
        """À appeler régulièrement : détecte les comptes disparus (une seule alerte chacun)."""
        if self.pause or not reglages.get("surveillance_active", True):
            return []
        delai_s = max(1, int(reglages.get("delai_absence_min", 3))) * 60
        alertes = []
        for e in self._etats.values():
            if e.absent_signale or e.depuis(maintenant) < delai_s:
                continue
            e.absent_signale = True
            if e.derniere_vue is not None and e.derniere_vue >= e.reference:
                detail = f"Aucune mission depuis <t:{int(e.derniere_vue)}:R>."
            else:
                detail = (
                    f"Pas vu depuis le démarrage de la surveillance (<t:{int(e.reference)}:R>)."
                )
            alertes.append(
                Alerte(
                    type="disparition",
                    compte=e.nom,
                    titre=f"🔴 {e.nom} a disparu",
                    texte=detail,
                    ping=bool(reglages.get("ping_disparition", True)),
                    couleur=ROUGE,
                    horodatage=maintenant,
                )
            )
        return alertes

    # ------------------------------------------------------------ mission reçue

    def mission_recue(
        self,
        mission: Mission,
        reglages: Mapping[str, Any],
        maintenant: float,
        anomalies: Sequence[Anomalie] = (),
    ) -> list[Alerte]:
        """Met à jour l'état du compte et renvoie les alertes à envoyer."""
        e = self.etat(mission.compte)
        if e is None:
            return []  # compte non surveillé
        actif = not self.pause and bool(reglages.get("surveillance_active", True))
        alertes: list[Alerte] = []

        # 1) Retour d'un compte absent
        if e.absent_signale:
            e.absent_signale = False
            if actif and reglages.get("message_retour", True):
                absence = ""
                if e.derniere_vue is not None:
                    absence = (
                        f" après {formater_duree(mission.horodatage - e.derniere_vue)} d'absence"
                    )
                alertes.append(
                    Alerte(
                        "retour",
                        e.nom,
                        f"🟢 {e.nom} est de retour",
                        f"Nouvelle mission reçue{absence}.",
                        bool(reglages.get("ping_retour", False)),
                        VERT,
                        maintenant,
                    )
                )
        if e.derniere_vue is None or mission.horodatage >= e.derniere_vue:
            e.derniere_vue = mission.horodatage

        # 2) Changement de zone
        ancienne, nouvelle = zone_est_safe(e.zone), zone_est_safe(mission.zone)
        if mission.zone:
            if actif and ancienne is not None and nouvelle is not None and ancienne != nouvelle:
                ping = bool(reglages.get("ping_zone", True))
                if nouvelle:
                    alertes.append(
                        Alerte(
                            "zone_retour",
                            e.nom,
                            f"🛡️ {e.nom} est revenu en zone Safe",
                            f"Zone : `{e.zone}` → `{mission.zone}`",
                            ping,
                            VERT,
                            maintenant,
                        )
                    )
                else:
                    alertes.append(
                        Alerte(
                            "zone_quitte",
                            e.nom,
                            f"🚨 {e.nom} a quitté la zone Safe",
                            f"Zone : `{e.zone}` → `{mission.zone}`",
                            ping,
                            ROUGE,
                            maintenant,
                        )
                    )
            e.zone = mission.zone

        if not actif:
            return alertes

        # 3) Drops rares
        raretes = reglages.get("raretes") or []
        rarete_min = str(reglages.get("rarete_min", "Legendary"))
        rares = [d for d in mission.drops if est_rare(d.rarete, rarete_min, raretes)]
        if rares:
            lignes = "\n".join(
                f"🎁 **{d.nom}** ({normaliser_rarete(d.rarete, raretes) or d.rarete})"
                + (f" ×{d.quantite}" if d.quantite > 1 else "")
                for d in rares
            )
            alertes.append(
                Alerte(
                    "drop",
                    e.nom,
                    f"✨ Drop rare pour {e.nom} !",
                    lignes,
                    bool(reglages.get("ping_drop", True)),
                    VIOLET,
                    maintenant,
                )
            )

        # 4) Anomalies (une seule alerte par type tant qu'elle dure, max 1 / 30 min)
        presentes = {a.type for a in anomalies}
        for type_ in list(e.anomalies):
            if (
                type_ not in presentes
                and maintenant - e.anomalies[type_] >= DELAI_REPETITION_ANOMALIE_S
            ):
                del e.anomalies[type_]
        for a in anomalies:
            if a.type in e.anomalies:
                continue
            e.anomalies[a.type] = maintenant
            alertes.append(
                Alerte(
                    "anomalie",
                    e.nom,
                    f"⚠️ Anomalie sur {e.nom}",
                    a.texte,
                    bool(reglages.get("ping_anomalies", True)),
                    ORANGE,
                    maintenant,
                )
            )
        return alertes
