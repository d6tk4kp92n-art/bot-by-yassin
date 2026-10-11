"""Calculs : rythmes, estimations, statistiques, anomalies.

Que des fonctions pures : on leur donne des missions, elles renvoient des chiffres.
Toutes les durées sont en secondes, tous les horodatages en secondes UNIX.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from bot.config import ALIAS_RARETES, FUSEAU, RARETES_DEFAUT
from bot.parser import Mission

RECUL_MIN_S = 120  # pas d'estimation avant 2 minutes de recul
FENETRE_RYTHME_S = 30 * 60  # le rythme est calculé sur les 30 dernières minutes


# ---------------------------------------------------------------- Raretés


def normaliser_rarete(rarete: str | None, raretes: Sequence[str] = RARETES_DEFAUT) -> str | None:
    """« mythical » -> « Mythic », « RARE » -> « Rare ». None si inconnue."""
    if not rarete:
        return None
    cle = rarete.strip().casefold()
    cle = ALIAS_RARETES.get(cle, cle).casefold()
    for r in raretes:
        if r.casefold() == cle:
            return r
    return None


def rang_rarete(rarete: str | None, raretes: Sequence[str] = RARETES_DEFAUT) -> int:
    """Position dans la liste (0 = la plus commune). -1 si inconnue."""
    nom = normaliser_rarete(rarete, raretes)
    return list(raretes).index(nom) if nom else -1


def est_rare(rarete: str | None, rarete_min: str, raretes: Sequence[str] = RARETES_DEFAUT) -> bool:
    """True si l'objet atteint (ou dépasse) la rareté minimum choisie."""
    rang = rang_rarete(rarete, raretes)
    seuil = rang_rarete(rarete_min, raretes)
    return rang >= 0 and seuil >= 0 and rang >= seuil


# ---------------------------------------------------------------- Rythmes


def taux_par_heure(
    points: Sequence[tuple[float, float]],
    maintenant: float,
    fenetre_s: float = FENETRE_RYTHME_S,
    recul_min_s: float = RECUL_MIN_S,
) -> float | None:
    """Rythme horaire d'une valeur gagnée à chaque mission (gold, xp, 1 par mission...).

    `points` = [(horodatage, valeur gagnée)] triés. S'il existe un point AVANT la fenêtre,
    on a assez d'historique : on divise ce qui a été gagné dans la fenêtre par la fenêtre.
    Sinon (début de farm), on part de la première mission vue, sans la compter
    (on ne sait pas quand elle a commencé). Renvoie None s'il y a moins de 2 min de recul.
    """
    debut = maintenant - fenetre_s
    if not points:
        return None
    avant = [p for p in points if p[0] < debut]
    dedans = [p for p in points if debut <= p[0] <= maintenant]
    if avant:
        duree = fenetre_s
        total = sum(v for _, v in dedans)
    else:
        if not dedans:
            return None
        duree = maintenant - dedans[0][0]
        total = sum(v for _, v in dedans[1:])
    if duree < recul_min_s:
        return None
    return total * 3600.0 / duree


def taux_total_par_heure(
    points: Sequence[tuple[float, float]],
    maintenant: float,
    fenetre_s: float = FENETRE_RYTHME_S,
    recul_min_s: float = RECUL_MIN_S,
) -> float | None:
    """Rythme horaire d'un TOTAL (ex. gems du compte) : différence entre début et fin."""
    debut = maintenant - fenetre_s
    if not points:
        return None
    avant = [p for p in points if p[0] < debut]
    dedans = [p for p in points if debut <= p[0] <= maintenant]
    if not dedans:
        return None
    if avant:
        reference = avant[-1][1]
        duree = fenetre_s
    else:
        reference = dedans[0][1]
        duree = maintenant - dedans[0][0]
    if duree < recul_min_s:
        return None
    return max(0.0, dedans[-1][1] - reference) * 3600.0 / duree


@dataclass
class Rythme:
    """Gains par heure d'un compte."""

    gold_h: float = 0.0
    xp_h: float = 0.0
    gems_h: float = 0.0
    missions_h: float = 0.0


def rythme(
    missions: Sequence[Mission],
    maintenant: float,
    fenetre_s: float = FENETRE_RYTHME_S,
) -> Rythme | None:
    """Rythme d'un compte au cours des `fenetre_s` dernières secondes. None si pas assez de recul."""
    triees = sorted(missions, key=lambda m: m.horodatage)
    missions_h = taux_par_heure([(m.horodatage, 1.0) for m in triees], maintenant, fenetre_s)
    if missions_h is None:
        return None
    gold_h = taux_par_heure(
        [(m.horodatage, float(m.gold or 0)) for m in triees], maintenant, fenetre_s
    )
    xp_h = taux_par_heure([(m.horodatage, float(m.xp or 0)) for m in triees], maintenant, fenetre_s)
    gems = [(m.horodatage, float(m.gems_total)) for m in triees if m.gems_total is not None]
    gems_h = taux_total_par_heure(gems, maintenant, fenetre_s) if gems else 0.0
    return Rythme(
        gold_h=gold_h or 0.0, xp_h=xp_h or 0.0, gems_h=gems_h or 0.0, missions_h=missions_h
    )


@dataclass
class Estimation:
    """Ce qu'un compte devrait gagner en `heures` heures."""

    heures: float
    gold: int
    xp: int
    gems: int
    missions: int


def estimer(r: Rythme, heures: float) -> Estimation:
    return Estimation(
        heures=heures,
        gold=round(r.gold_h * heures),
        xp=round(r.xp_h * heures),
        gems=round(r.gems_h * heures),
        missions=round(r.missions_h * heures),
    )


def additionner_estimations(estimations: Iterable[Estimation], heures: float) -> Estimation:
    total = Estimation(heures, 0, 0, 0, 0)
    for e in estimations:
        total.gold += e.gold
        total.xp += e.xp
        total.gems += e.gems
        total.missions += e.missions
    return total


# ---------------------------------------------------------------- Gains d'une période


@dataclass
class Gains:
    """Ce qu'un compte a gagné sur une liste de missions."""

    missions: int = 0
    gold: int = 0
    xp: int = 0
    gems: int = 0
    duree_moyenne_s: float | None = None
    objets: Counter[str] = field(default_factory=Counter)  # rareté -> quantité
    record_gold: int = 0


def gains(missions: Sequence[Mission], raretes: Sequence[str] = RARETES_DEFAUT) -> Gains:
    """Totaux sur une liste de missions (d'un seul compte)."""
    triees = sorted(missions, key=lambda m: m.horodatage)
    g = Gains(missions=len(triees))
    g.gold = sum(m.gold or 0 for m in triees)
    g.xp = sum(m.xp or 0 for m in triees)
    g.record_gold = max((m.gold or 0 for m in triees), default=0)
    totaux = [m.gems_total for m in triees if m.gems_total is not None]
    if len(totaux) >= 2:
        g.gems = max(0, totaux[-1] - totaux[0])
    durees = [m.duree_s for m in triees if m.duree_s]
    g.duree_moyenne_s = statistics.fmean(durees) if durees else None
    for m in triees:
        for d in m.drops:
            g.objets[normaliser_rarete(d.rarete, raretes) or d.rarete] += d.quantite
    return g


def temps_actif(horodatages: Sequence[float], seuil_s: float, fin: float | None = None) -> float:
    """Temps de jeu effectif : on additionne les écarts entre missions qui sont
    plus petits que le seuil d'absence (au-delà, le compte était considéré absent)."""
    ts = sorted(horodatages)
    total = 0.0
    for a, b in zip(ts, ts[1:], strict=False):
        if b - a <= seuil_s:
            total += b - a
    if ts and fin is not None and 0 <= fin - ts[-1] <= seuil_s:
        total += fin - ts[-1]
    return total


def meilleure_heure(missions: Sequence[Mission]) -> tuple[int, int] | None:
    """Heure de la journée (heure belge) où le compte a gagné le plus de gold en moyenne.

    Renvoie (heure, gold moyen gagné pendant cette heure-là chaque jour)."""
    par_heure: dict[int, int] = defaultdict(int)
    jours_par_heure: dict[int, set[str]] = defaultdict(set)
    for m in missions:
        dt = datetime.fromtimestamp(m.horodatage, FUSEAU)
        par_heure[dt.hour] += m.gold or 0
        jours_par_heure[dt.hour].add(dt.date().isoformat())
    if not par_heure:
        return None
    moyennes = {h: total / max(1, len(jours_par_heure[h])) for h, total in par_heure.items()}
    heure = max(moyennes, key=lambda h: moyennes[h])
    return heure, round(moyennes[heure])


@dataclass
class StatsCompte:
    """Statistiques d'un compte sur une période."""

    compte: str
    gains: Gains
    temps_actif_s: float
    duree_periode_s: float
    meilleure_heure: tuple[int, int] | None

    @property
    def disponibilite(self) -> float:
        """Pourcentage du temps où le compte était actif (0 à 100)."""
        if self.duree_periode_s <= 0:
            return 0.0
        return max(0.0, min(100.0, 100.0 * self.temps_actif_s / self.duree_periode_s))

    def par_heure(self, valeur: float) -> float:
        """Moyenne par heure de jeu effectif."""
        if self.temps_actif_s < 60:
            return 0.0
        return valeur * 3600.0 / self.temps_actif_s


def stats_compte(
    compte: str,
    missions: Sequence[Mission],
    debut: float,
    fin: float,
    seuil_absence_s: float,
    raretes: Sequence[str] = RARETES_DEFAUT,
) -> StatsCompte:
    """Stats complètes d'un compte entre `debut` et `fin`."""
    dans = [m for m in missions if debut <= m.horodatage <= fin]
    actif = temps_actif([m.horodatage for m in dans], seuil_absence_s, fin)
    return StatsCompte(
        compte=compte,
        gains=gains(dans, raretes),
        temps_actif_s=actif,
        duree_periode_s=max(0.0, fin - debut),
        meilleure_heure=meilleure_heure(dans),
    )


# ---------------------------------------------------------------- Anomalies

PARAMS_SENSIBILITE: dict[str, dict[str, float]] = {
    # facteur_lent : mission « lente » si > facteur × la moyenne
    # chute        : alerte si les gains récents baissent de plus de X %
    # bloque       : nombre de missions d'affilée sans que les totaux bougent
    "basse": {"facteur_lent": 3.0, "chute": 0.7, "bloque": 8},
    "normale": {"facteur_lent": 2.0, "chute": 0.5, "bloque": 5},
    "haute": {"facteur_lent": 1.5, "chute": 0.3, "bloque": 3},
}


@dataclass(frozen=True)
class Anomalie:
    type: str  # "lent", "chute", "bloque"
    texte: str


def detecter_anomalies(missions: Sequence[Mission], sensibilite: str = "normale") -> list[Anomalie]:
    """Cherche des comportements anormaux dans les dernières missions d'UN compte."""
    p = PARAMS_SENSIBILITE.get(sensibilite, PARAMS_SENSIBILITE["normale"])
    triees = sorted(missions, key=lambda m: m.horodatage)
    resultat: list[Anomalie] = []

    # 1) Missions anormalement lentes
    durees = [m.duree_s for m in triees if m.duree_s]
    if len(durees) >= 6:
        precedentes = durees[-21:-1]
        moyenne = statistics.fmean(precedentes)
        if moyenne > 0 and durees[-1] > p["facteur_lent"] * moyenne:
            resultat.append(
                Anomalie(
                    "lent",
                    f"Mission très lente : {formater_duree(durees[-1])} "
                    f"(moyenne {formater_duree(moyenne)})",
                )
            )

    # 2) Chute des gains
    golds = [m.gold for m in triees if m.gold is not None]
    if len(golds) >= 10:
        recents = statistics.fmean(golds[-5:])
        avant = statistics.fmean(golds[-25:-5])
        if avant > 0 and recents < (1 - p["chute"]) * avant:
            baisse = 100 * (1 - recents / avant)
            resultat.append(
                Anomalie(
                    "chute",
                    f"Gains en chute de {baisse:.0f} % "
                    f"(moyenne {formater_nombre(avant)} → {formater_nombre(recents)} gold)",
                )
            )

    # 3) Compte bloqué : les totaux ne bougent plus alors que les missions continuent
    n = int(p["bloque"])
    dernieres = triees[-n:]
    if len(dernieres) >= n and n >= 2:
        totaux = {(m.gold_total, m.gems_total, m.level, m.prestige) for m in dernieres}
        tous_connus = all(m.gold_total is not None for m in dernieres)
        gagne = sum(m.gold or 0 for m in dernieres[1:])
        if tous_connus and len(totaux) == 1 and gagne > 0:
            resultat.append(
                Anomalie(
                    "bloque", f"Les totaux ne bougent plus depuis {n} missions (compte bloqué ?)"
                )
            )
    return resultat


# ---------------------------------------------------------------- Objectifs


def date_atteinte(
    actuel: float, cible: float, taux_h: float | None, maintenant: float
) -> float | None:
    """Horodatage estimé où l'objectif sera atteint. None si impossible à estimer."""
    if actuel >= cible:
        return maintenant
    if not taux_h or taux_h <= 0:
        return None
    heures = (cible - actuel) / taux_h
    if not math.isfinite(heures) or heures > 24 * 365 * 5:
        return None
    return maintenant + heures * 3600


def progression(actuel: float, depart: float, cible: float) -> float:
    """Avancement de 0.0 à 1.0 entre la valeur de départ et la cible."""
    if cible <= depart:
        return 1.0 if actuel >= cible else 0.0
    return max(0.0, min(1.0, (actuel - depart) / (cible - depart)))


# ---------------------------------------------------------------- Petits formats


def formater_nombre(valeur: float | None) -> str:
    """37807 -> « 37 807 » (espace fine insécable comme séparateur des milliers)."""
    if valeur is None:
        return "—"
    return f"{round(valeur):,}".replace(",", "\u202f")


def formater_duree(secondes: float | None) -> str:
    """64 -> « 1 min 04 s » ; 3723 -> « 1 h 02 min »."""
    if secondes is None:
        return "—"
    s = int(round(secondes))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min {s % 60:02d} s"
    h, reste = divmod(s, 3600)
    if h < 48:
        return f"{h} h {reste // 60:02d} min"
    return f"{h // 24} j {h % 24} h"


# ---------------------------------------------------------------- Périodes

PERIODES: dict[str, str] = {
    "session": "Session (depuis le démarrage du bot)",
    "aujourdhui": "Aujourd'hui",
    "7j": "7 derniers jours",
    "30j": "30 derniers jours",
    "tout": "Depuis toujours",
}


def bornes_periode(
    periode: str, maintenant: float, demarrage: float, premiere: float | None = None
) -> tuple[float, float]:
    """Renvoie (début, fin) d'une période. `premiere` = date de la toute première mission."""
    if periode == "session":
        return demarrage, maintenant
    if periode == "aujourdhui":
        minuit = datetime.fromtimestamp(maintenant, FUSEAU).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return minuit.timestamp(), maintenant
    if periode == "7j":
        return maintenant - 7 * 86400, maintenant
    if periode == "30j":
        return maintenant - 30 * 86400, maintenant
    return (premiere if premiere is not None else demarrage), maintenant


# ---------------------------------------------------------------- Records


def gold_par_jour(missions: Sequence[Mission]) -> dict[str, int]:
    """Gold gagné par jour (heure belge) : {"2026-07-01": 123456}."""
    jours: dict[str, int] = defaultdict(int)
    for m in missions:
        jours[datetime.fromtimestamp(m.horodatage, FUSEAU).date().isoformat()] += m.gold or 0
    return dict(jours)


def records_battus(compte: str, periode: Sequence[Mission], avant: Sequence[Mission]) -> list[str]:
    """Records battus pendant `periode` par rapport à tout ce qui s'est passé `avant`."""
    records = []
    if not periode or not avant:
        return records  # pas de record possible sans historique pour comparer
    meilleur = max(periode, key=lambda m: m.gold or 0)
    ancien = max((m.gold or 0 for m in avant), default=0)
    if (meilleur.gold or 0) > ancien:
        records.append(
            f"💰 **{compte}** : record de gold en une mission → {formater_nombre(meilleur.gold)} "
            f"(ancien : {formater_nombre(ancien)})"
        )
    jours_periode = gold_par_jour(periode)
    jours_avant = gold_par_jour(avant)
    if jours_periode and jours_avant:
        jour, total = max(jours_periode.items(), key=lambda p: p[1])
        ancien_jour = max((v for k, v in jours_avant.items() if k != jour), default=0)
        if ancien_jour and total > ancien_jour:
            records.append(
                f"📅 **{compte}** : meilleure journée → {formater_nombre(total)} gold le "
                f"{datetime.fromisoformat(jour).strftime('%d/%m')} (ancien : {formater_nombre(ancien_jour)})"
            )
    durees = [m.duree_s for m in periode if m.duree_s]
    durees_avant = [m.duree_s for m in avant if m.duree_s]
    if durees and durees_avant and min(durees) < min(durees_avant):
        records.append(
            f"⏱️ **{compte}** : mission la plus rapide → {formater_duree(min(durees))} "
            f"(ancien : {formater_duree(min(durees_avant))})"
        )
    return records
